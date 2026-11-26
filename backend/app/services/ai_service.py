import json
import logging
import math
import re
import time
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import SkillSphereException


logger = logging.getLogger(__name__)

AI_REQUEST_BUDGET_SECONDS = 24.0
AI_ATTEMPT_TIMEOUT_SECONDS = 10.0
AI_MAX_ATTEMPTS = 2
AI_MIN_RETRY_ATTEMPT_SECONDS = 0.25


class AIService:
    """Gemini-only AI integration shared by SkillSphere features."""

    # -----------------------------------------------------
    # PROVIDER CONFIGURATION
    # -----------------------------------------------------

    @staticmethod
    def _provider(provider: Optional[str] = None) -> str:
        selected = (
            provider or settings.AI_PROVIDER or "google_gemini"
        ).strip().lower()

        aliases = {
            "gemini": "google_gemini",
            "google": "google_gemini",
        }

        selected = aliases.get(selected, selected)

        if selected != "google_gemini":
            raise SkillSphereException(
                400,
                "Only Google Gemini is supported for AI generation."
            )

        return selected

    # -----------------------------------------------------
    # API KEY
    # -----------------------------------------------------

    @classmethod
    def _api_key(cls, provider: Optional[str] = None) -> str:
        cls._provider(provider)
        key = getattr(settings, "GEMINI_API_KEY", None) or settings.AI_API_KEY

        if not key or not key.strip():
            raise SkillSphereException(
                503,
                "Gemini API key is not configured in the backend environment."
            )

        return key.strip()

    # -----------------------------------------------------
    # PROVIDER CONFIGURATION STATUS
    # -----------------------------------------------------

    @classmethod
    def is_configured(cls, provider: Optional[str] = None) -> bool:
        try:
            cls._api_key(provider)
            return True
        except SkillSphereException:
            return False

    # -----------------------------------------------------
    # AI REQUEST
    # -----------------------------------------------------

    @staticmethod
    def _safe_request_id(response) -> Optional[str]:
        headers = getattr(response, "headers", {}) or {}
        request_id = (
            headers.get("x-goog-request-id")
            or headers.get("x-request-id")
            or headers.get("request-id")
        )
        if not request_id:
            return None
        # Keep provider correlation IDs useful while preventing log injection.
        return re.sub(r"[^A-Za-z0-9._:-]", "", str(request_id))[:80] or None

    @staticmethod
    def _retry_after_seconds(response) -> Optional[float]:
        value = (getattr(response, "headers", {}) or {}).get("Retry-After")
        if not value:
            return None
        try:
            seconds = float(value)
            return seconds if math.isfinite(seconds) and seconds >= 0 else None
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(str(value))
                if retry_at.tzinfo is None:
                    return None
                return max(0.0, retry_at.timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                return None

    @classmethod
    def _post_with_retry(cls, client, url: str, provider: str, model: str, **kwargs):
        """Make bounded provider attempts; never log request content or credentials."""
        deadline = time.monotonic() + AI_REQUEST_BUDGET_SECONDS
        for attempt in range(AI_MAX_ATTEMPTS):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise httpx.TimeoutException("AI request time budget exceeded")
            attempt_timeout = min(AI_ATTEMPT_TIMEOUT_SECONDS, remaining)
            request_kwargs = {
                **kwargs,
                "timeout": httpx.Timeout(
                    attempt_timeout,
                    connect=min(3.0, attempt_timeout),
                    write=min(5.0, attempt_timeout),
                    pool=min(2.0, attempt_timeout),
                ),
            }
            try:
                response = client.post(url, **request_kwargs)
                if time.monotonic() > deadline:
                    raise httpx.TimeoutException("AI request time budget exceeded")
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                is_retryable = status in {408, 429} or 500 <= status < 600
                if attempt + 1 >= AI_MAX_ATTEMPTS or not is_retryable:
                    raise
                retry_after = cls._retry_after_seconds(exc.response)
                delay = retry_after if retry_after is not None else min(0.5 * (2 ** attempt), 1.0)
                remaining = deadline - time.monotonic()
                if remaining - delay < AI_MIN_RETRY_ATTEMPT_SECONDS:
                    raise
                logger.warning(
                    "Transient AI provider failure; retrying (provider=%s, model=%s, attempt=%s, status=%s, request_id=%s).",
                    provider,
                    model,
                    attempt + 1,
                    status,
                    cls._safe_request_id(exc.response) or "unavailable",
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 >= AI_MAX_ATTEMPTS:
                    raise
                delay = min(0.25 * (2 ** attempt), 0.5)
                if deadline - time.monotonic() - delay < AI_MIN_RETRY_ATTEMPT_SECONDS:
                    raise
                logger.warning(
                    "Transient AI network failure; retrying (provider=%s, model=%s, attempt=%s, error_type=%s).",
                    provider,
                    model,
                    attempt + 1,
                    type(exc).__name__,
                )
            time.sleep(delay)

    @classmethod
    def _request_text(
        cls,
        prompt: str,
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:

        selected = cls._provider(provider)
        key = cls._api_key(selected)

        try:
            with httpx.Client(timeout=AI_ATTEMPT_TIMEOUT_SECONDS) as client:
                # ---------------- GEMINI ----------------

                model = getattr(
                    settings,
                    "GEMINI_MODEL",
                    "gemini-3.8-flash"
                )

                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.4,
                        "responseMimeType": "application/json",
                    },
                }

                if system_prompt:
                    payload["systemInstruction"] = {
                        "parts": [
                            {"text": system_prompt}
                        ]
                    }

                response = cls._post_with_retry(
                    client,
                    (
                        "https://generativelanguage.googleapis.com/"
                        f"v1beta/models/{model}:generateContent"
                    ),
                    selected,
                    model,
                    # Google documents x-goog-api-key for this API. Keeping
                    # credentials out of query strings prevents HTTP client
                    # request logging from exposing them.
                    headers={"x-goog-api-key": key},
                    json=payload,
                )

                response_data = response.json()

                candidates = response_data.get("candidates", [])

                if not candidates:
                    logger.warning(
                        "Gemini returned no candidates (provider=%s, model=%s, request_id=%s).",
                        selected,
                        model,
                        cls._safe_request_id(response) or "unavailable",
                    )
                    raise SkillSphereException(
                        502,
                        "Gemini could not provide an answer to this request. Please rephrase it and try again."
                    )

                parts = candidates[0].get("content", {}).get("parts", [])
                content = "\n".join(
                    part["text"]
                    for part in parts
                    if isinstance(part, dict) and isinstance(part.get("text"), str)
                ).strip()

                if not content:
                    logger.warning(
                        "Gemini returned no text content (provider=%s, model=%s, request_id=%s).",
                        selected,
                        model,
                        cls._safe_request_id(response) or "unavailable",
                    )
                    raise SkillSphereException(
                        502,
                        "Gemini returned an empty response. Please try again shortly."
                    )

                return content

        except SkillSphereException as exc:
            logger.warning(
                "AI provider returned a sanitized application error (provider=%s, model=%s, status=%s).",
                selected,
                model if "model" in locals() else "unavailable",
                exc.status_code,
            )
            raise

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            request_id = cls._safe_request_id(exc.response) or "unavailable"
            logger.warning(
                "AI provider HTTP failure (provider=%s, model=%s, status=%s, request_id=%s).",
                selected,
                model if "model" in locals() else "unavailable",
                status,
                request_id,
            )
            messages = {
                400: (400, "Gemini rejected the request (HTTP 400). Check the request or model configuration."),
                401: (401, "Gemini authentication failed (HTTP 401). Check backend credentials."),
                403: (403, "Gemini access is forbidden (HTTP 403). Check project and model access."),
                404: (404, "The configured Gemini model or endpoint was not found (HTTP 404). Check GEMINI_MODEL."),
                408: (504, "Gemini timed out while processing the request. Please try again shortly."),
                429: (429, "Gemini rate limit reached (HTTP 429). Please wait before trying again."),
            }
            status_code, detail = messages.get(
                status,
                (503, f"Gemini is temporarily unavailable (HTTP {status}). Please try again shortly."),
            )
            raise SkillSphereException(status_code, detail) from None

        except httpx.TimeoutException as exc:
            logger.warning(
                "AI provider request timed out (provider=%s, model=%s, error_type=%s).",
                selected,
                model if "model" in locals() else "unavailable",
                type(exc).__name__,
            )

            raise SkillSphereException(
                504,
                "Gemini request timed out within its response budget. Please try again shortly."
            )

        except httpx.TransportError as exc:
            logger.warning(
                "AI provider network failure (provider=%s, model=%s, error_type=%s).",
                selected,
                model if "model" in locals() else "unavailable",
                type(exc).__name__,
            )
            raise SkillSphereException(
                503,
                "Gemini could not be reached because of a network error. Please try again shortly.",
            ) from None

        except Exception as exc:
            logger.warning(
                "AI provider request failed (provider=%s, model=%s, error_type=%s).",
                selected,
                model if "model" in locals() else "unavailable",
                type(exc).__name__,
            )

            raise SkillSphereException(
                502,
                "Gemini returned an invalid response. Please try again shortly.",
            ) from None

    # -----------------------------------------------------
    # Sphera provider failures are surfaced instead of replaced with canned content.

    # JSON RESPONSE PARSER
    # -----------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:

        if not text or not isinstance(text, str):
            raise SkillSphereException(
                502,
                "AI returned an empty response. Please try again."
            )

        cleaned = text.strip()

        # Remove Markdown JSON code fences
        cleaned = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```\s*$",
            "",
            cleaned,
        ).strip()

        # First attempt: parse complete response
        try:
            data = json.loads(cleaned)

        except json.JSONDecodeError:
            data = None

        # If extra text exists, extract JSON object
        if data is None:

            decoder = json.JSONDecoder()
            data = None

            for index, character in enumerate(cleaned):

                if character != "{":
                    continue

                try:
                    candidate, _ = decoder.raw_decode(
                        cleaned[index:]
                    )

                    if isinstance(candidate, dict):
                        data = candidate
                        break

                except json.JSONDecodeError:
                    continue

        if data is None:
            raise SkillSphereException(
                502,
                "AI returned an invalid response format. Please try again."
            )

        if not isinstance(data, dict):
            raise SkillSphereException(
                502,
                "AI returned an unexpected response format."
            )

        return data

    # -----------------------------------------------------
    # AI MCQ QUESTION GENERATION
    # -----------------------------------------------------

    @classmethod
    def generate_mcq_questions(
        cls,
        topic: str,
        difficulty: str = "Medium",
        count: int = 5,
        question_type: str = "Mixed",
        provider: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        allowed_difficulties = {
            "Easy",
            "Medium",
            "Hard",
        }

        allowed_types = {
            "Mixed",
            "Conceptual",
            "Code Snippet",
            "Fill in the Blank",
            "Scenario-based",
        }

        # Validate difficulty
        if difficulty not in allowed_difficulties:
            raise SkillSphereException(
                400,
                "Difficulty must be Easy, Medium, or Hard."
            )

        # Validate question type
        if question_type not in allowed_types:
            raise SkillSphereException(
                400,
                "Invalid question type."
            )

        # Validate count
        if not isinstance(count, int) or not 1 <= count <= 20:
            raise SkillSphereException(
                400,
                "Question count must be between 1 and 20."
            )

        # Validate topic
        topic = (topic or "").strip()

        if len(topic) < 2:
            raise SkillSphereException(
                400,
                "Please enter a valid topic or technology."
            )

        # AI generation prompt
        prompt = f"""
Create exactly {count} original technical MCQ questions about: {topic}.

Difficulty: {difficulty}.
Question style: {question_type}.

If style is Mixed, include a balanced mix of conceptual,
code-snippet, fill-in-the-blank and scenario-based questions
where appropriate.

All questions must be objective MCQs.

Do not ask candidates to:
- Type code.
- Write long answers.
- Provide descriptive answers.

Each question must have exactly four distinct, non-empty options
and exactly one unambiguous correct answer.

For every question:
- question_type must be exactly one of:
  Conceptual, Code Snippet, Fill in the Blank, Scenario-based.
- marks must be a positive number.
- correct_answer must be exactly A, B, C, or D.
- explanation must support the correct answer.
- Avoid duplicate and near-duplicate questions.

Return JSON only in this structure:

{{
  "questions": [
    {{
      "question_text": "...",
      "category": "{topic}",
      "difficulty": "{difficulty}",
      "question_type": "Conceptual",
      "option_a": "...",
      "option_b": "...",
      "option_c": "...",
      "option_d": "...",
      "correct_answer": "A",
      "marks": 1,
      "explanation": "..."
    }}
  ]
}}

Do not include Markdown or text outside JSON.
"""

        # Request AI questions
        raw = cls._request_text(
            prompt,
            provider,
        )

        data = cls._parse_json(raw)

        items = data.get("questions")

        if not isinstance(items, list):
            raise SkillSphereException(
                502,
                "AI returned an invalid questions list. Please try again."
            )

        validated: List[Dict[str, Any]] = []
        seen_questions = set()

        valid_generated_types = (
            allowed_types - {"Mixed"}
        )

        # Validate generated questions
        for item in items:

            if not isinstance(item, dict):
                continue

            question_text = str(
                item.get("question_text", "")
            ).strip()

            category = str(
                item.get("category") or topic
            ).strip()

            generated_type = str(
                item.get("question_type", "")
            ).strip()

            options = {
                f"option_{letter}": str(
                    item.get(f"option_{letter}", "")
                ).strip()
                for letter in "abcd"
            }

            correct_answer = str(
                item.get("correct_answer", "")
            ).strip().upper()

            try:
                marks = float(
                    item.get("marks", 1.0)
                )

            except (TypeError, ValueError):
                continue

            normalized_question = re.sub(
                r"\W+",
                " ",
                question_text.lower(),
            ).strip()

            # Core validation
            if (
                len(question_text) < 5
                or not category
                or generated_type not in valid_generated_types
                or any(not value for value in options.values())
                or len({
                    value.casefold()
                    for value in options.values()
                }) != 4
                or correct_answer not in {"A", "B", "C", "D"}
                or not (marks > 0)
                or not normalized_question
                or normalized_question in seen_questions
            ):
                continue

            # Validate requested type
            if (
                question_type != "Mixed"
                and generated_type != question_type
            ):
                continue

            seen_questions.add(
                normalized_question
            )

            validated.append({
                "question_text": question_text,
                "category": category,
                "difficulty": difficulty,
                "question_type": generated_type,
                **options,
                "correct_answer": correct_answer,
                "marks": marks,
                "explanation": str(
                    item.get("explanation") or ""
                ).strip(),
            })

            if len(validated) == count:
                break

        # Ensure requested number of valid questions
        if len(validated) != count:

            logger.warning(
                "AI generated %s valid MCQs; %s requested for topic %r",
                len(validated),
                count,
                topic,
            )

            raise SkillSphereException(
                502,
                (
                    f"AI returned only {len(validated)} valid unique "
                    f"questions out of {count} requested. Please generate again."
                )
            )

        return validated

    # -----------------------------------------------------
    # INTERVIEW ANSWER EVALUATION
    # -----------------------------------------------------

    @classmethod
    def evaluate_interview_answer(
        cls,
        question: str,
        answer: str,
        role_or_tech: str,
    ) -> Dict[str, Any]:

        prompt = (
            f"Evaluate this interview answer for a {role_or_tech} role.\n"
            f"Question: {question}\n"
            f"Answer: {answer}\n"
            "Return JSON with score (0-100), feedback (2-3 sentences), "
            "strengths (string), improvements (string)."
        )

        data = cls._parse_json(
            cls._request_text(prompt)
        )

        try:
            score = float(
                data.get("score", 0)
            )

        except (TypeError, ValueError):
            score = 0

        score = max(
            0,
            min(100, score),
        )

        return {
            "score": score,
            "feedback": str(
                data.get("feedback", "")
            ),
            "strengths": data.get(
                "strengths",
                []
            ),
            "improvements": data.get(
                "improvements",
                []
            ),
        }

    # -----------------------------------------------------
    # INTERVIEW QUESTION GENERATION
    # -----------------------------------------------------

    @classmethod
    def generate_interview_questions(
        cls,
        role_or_tech: str,
        difficulty: str = "Intermediate",
        count: int = 5,
    ) -> List[Dict[str, str]]:

        prompt = (
            f"Generate {count} interview questions for "
            f"{role_or_tech} at {difficulty} difficulty. "
            'Return JSON {"questions":[{"question":"..."}]}.'
        )

        data = cls._parse_json(
            cls._request_text(prompt)
        )

        questions = data.get("questions", [])

        if not isinstance(questions, list):
            raise SkillSphereException(
                502,
                "AI returned an invalid interview questions list."
            )

        validated_questions = []

        for item in questions:

            if not isinstance(item, dict):
                continue

            question = str(
                item.get("question", "")
            ).strip()

            if question:
                validated_questions.append({
                    "question": question
                })

        return validated_questions
