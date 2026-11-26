import httpx
import pytest

from app.core.config import settings
from app.core.exceptions import SkillSphereException
from app.services.ai_service import AIService, AI_ATTEMPT_TIMEOUT_SECONDS, AI_REQUEST_BUDGET_SECONDS


class StubClient:
    def __init__(self, responses):
        self.responses = responses if isinstance(responses, list) else [responses]
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        response = self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        response.request = httpx.Request("POST", url)
        response.raise_for_status()
        return response


@pytest.fixture(autouse=True)
def no_real_waits(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.time.sleep", lambda _seconds: None)


def configure_gemini(monkeypatch, client):
    monkeypatch.setattr(settings, "AI_PROVIDER", "google_gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-secret-do-not-log")
    monkeypatch.setattr(settings, "AI_API_KEY", None)
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr("app.services.ai_service.httpx.Client", lambda **_kwargs: client)


def test_non_gemini_provider_is_rejected_without_network_request(monkeypatch):
    client = StubClient(httpx.Response(200, json={"candidates": []}))
    configure_gemini(monkeypatch, client)

    with pytest.raises(SkillSphereException) as error:
        AIService._request_text("synthetic prompt", provider="openai")

    assert error.value.status_code == 400
    assert "Only Google Gemini" in error.value.detail
    assert client.requests == []


def test_gemini_success_uses_secure_header_and_bounded_timeout(monkeypatch):
    client = StubClient(httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "synthetic response"}]}}]}))
    configure_gemini(monkeypatch, client)

    result = AIService._request_text("synthetic test prompt", system_prompt="synthetic system prompt")

    url, kwargs = client.requests[0]
    assert result == "synthetic response"
    assert "test-secret-do-not-log" not in url
    assert kwargs["headers"]["x-goog-api-key"] == "test-secret-do-not-log"
    assert kwargs["json"]["systemInstruction"]["parts"][0]["text"] == "synthetic system prompt"
    assert isinstance(kwargs["timeout"], httpx.Timeout)
    assert kwargs["timeout"].read <= AI_ATTEMPT_TIMEOUT_SECONDS
    assert AI_REQUEST_BUDGET_SECONDS < 30


@pytest.mark.parametrize("status_code", [408, 429, 500, 501, 502, 503, 504, 599])
def test_transient_status_retries_once_then_succeeds(monkeypatch, status_code):
    client = StubClient([
        httpx.Response(status_code, json={"error": {"message": "provider body must not be logged"}}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "retry succeeded"}]}}]}),
    ])
    configure_gemini(monkeypatch, client)

    assert AIService._request_text("synthetic prompt") == "retry succeeded"
    assert len(client.requests) == 2


def test_retry_after_is_honored_for_rate_limit(monkeypatch):
    delays = []
    monkeypatch.setattr("app.services.ai_service.time.sleep", delays.append)
    client = StubClient([
        httpx.Response(429, headers={"Retry-After": "2"}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}),
    ])
    configure_gemini(monkeypatch, client)

    assert AIService._request_text("synthetic prompt") == "ok"
    assert delays == [2.0]
    assert len(client.requests) == 2


def test_http_date_retry_after_is_honored(monkeypatch):
    delays = []
    monkeypatch.setattr("app.services.ai_service.time.sleep", delays.append)
    monkeypatch.setattr("app.services.ai_service.time.time", lambda: 0.0)
    client = StubClient([
        httpx.Response(503, headers={"Retry-After": "Thu, 01 Jan 1970 00:00:05 GMT"}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}),
    ])
    configure_gemini(monkeypatch, client)

    assert AIService._request_text("synthetic prompt") == "ok"
    assert delays == [5.0]


def test_retry_after_beyond_budget_does_not_retry_early(monkeypatch):
    client = StubClient(httpx.Response(429, headers={"Retry-After": "60"}))
    configure_gemini(monkeypatch, client)

    with pytest.raises(SkillSphereException) as error:
        AIService._request_text("synthetic prompt")

    assert error.value.status_code == 429
    assert "rate limit" in error.value.detail.lower()
    assert len(client.requests) == 1


def test_response_after_overall_deadline_is_rejected(monkeypatch):
    clock = {"now": 0.0}

    def monotonic():
        return clock["now"]

    class SlowClient(StubClient):
        def post(self, url, **kwargs):
            clock["now"] = AI_REQUEST_BUDGET_SECONDS + 0.1
            return super().post(url, **kwargs)

    monkeypatch.setattr("app.services.ai_service.time.monotonic", monotonic)
    client = SlowClient(httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "too late"}]}}]}))
    configure_gemini(monkeypatch, client)

    with pytest.raises(SkillSphereException) as error:
        AIService._request_text("synthetic prompt")

    assert error.value.status_code == 504
    assert len(client.requests) == 1


@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
def test_permanent_http_errors_are_not_retried(monkeypatch, status_code):
    client = StubClient(httpx.Response(status_code, json={"error": {"message": "sensitive provider body"}}))
    configure_gemini(monkeypatch, client)

    with pytest.raises(SkillSphereException) as error:
        AIService._request_text("synthetic prompt")

    assert error.value.status_code == status_code
    assert len(client.requests) == 1
    assert "sensitive provider body" not in error.value.detail
    assert "test-secret-do-not-log" not in error.value.detail


@pytest.mark.parametrize("exception", [httpx.ReadTimeout("synthetic timeout"), httpx.ConnectError("synthetic network error")])
def test_timeout_and_network_failures_retry_once_then_return_clear_error(monkeypatch, exception):
    client = StubClient([exception, exception])
    configure_gemini(monkeypatch, client)

    with pytest.raises(SkillSphereException) as error:
        AIService._request_text("synthetic prompt")

    assert error.value.status_code in {503, 504}
    assert "Gemini" in error.value.detail
    assert len(client.requests) == 2


def test_repeated_503_returns_sanitized_error_and_safe_diagnostics(monkeypatch, caplog):
    key = "test-secret-do-not-log"
    prompt = "synthetic private prompt that must not be logged"
    client = StubClient([
        httpx.Response(503, headers={"x-request-id": "req-123"}, json={"error": {"message": key}}),
        httpx.Response(503, headers={"x-request-id": "req-456"}, json={"error": {"message": prompt}}),
    ])
    configure_gemini(monkeypatch, client)

    with pytest.raises(SkillSphereException) as error:
        AIService._request_text(prompt)

    assert error.value.status_code == 503
    assert "temporarily unavailable" in error.value.detail
    assert key not in error.value.detail
    assert prompt not in error.value.detail
    assert key not in caplog.text
    assert prompt not in caplog.text
    assert "req-456" in caplog.text
    assert all("generativelanguage.googleapis.com" in url for url, _ in client.requests)


def test_gemini_model_and_http_failure_details_are_sanitized(monkeypatch):
    client = StubClient(httpx.Response(404, json={"error": {"message": "provider details"}}))
    configure_gemini(monkeypatch, client)

    with pytest.raises(SkillSphereException) as error:
        AIService._request_text("synthetic prompt")

    assert error.value.status_code == 404
    assert "model or endpoint" in error.value.detail
    assert "provider details" not in error.value.detail
