from urllib.parse import urlsplit

import pytest
from pydantic import ValidationError

from app.core.config import (
    CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN,
    PRODUCTION_FRONTEND_ORIGIN,
    VERCEL_PREVIEW_ORIGIN_REGEX,
    VERCEL_PREVIEW_FRONTEND_ORIGIN,
    Settings,
)


def make_settings(**overrides):
    values = {
        "APP_ENV": "production",
        "DATABASE_HOST": "tidb.example.invalid",
        "DATABASE_PORT": 4000,
        "DATABASE_NAME": "synthetic_portal",
        "DATABASE_USER": "synthetic_user",
        "DATABASE_PASSWORD": "synthetic_password",
        "DATABASE_SSL_CA": "/synthetic/tidb-ca.pem",
        "SECRET_KEY": "synthetic-test-signing-key",
        "ADMIN_NAME": "Synthetic Admin",
        "ADMIN_EMAIL": "synthetic-admin@example.test",
        "ADMIN_PASSWORD": "synthetic-admin-password",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_cors_asgi_app():
    """Build the project's CORS middleware policy without starting the app."""
    from starlette.middleware.cors import CORSMiddleware

    settings = make_settings()
    return CORSMiddleware(
        lambda *_args: None,
        allow_origins=settings.ALLOWED_CORS_ORIGINS,
        allow_origin_regex=VERCEL_PREVIEW_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "0.0.0.0", "db.localhost"])
def test_production_rejects_loopback_database_hosts(host):
    with pytest.raises(ValidationError, match="remote database host"):
        make_settings(DATABASE_HOST=host)


def test_production_database_url_uses_explicit_remote_environment_coordinates():
    settings = make_settings()
    parsed = urlsplit(settings.DATABASE_URL)

    assert parsed.scheme == "mysql+pymysql"
    assert parsed.hostname == "tidb.example.invalid"
    assert parsed.port == 4000
    assert parsed.path == "/synthetic_portal"


def test_required_database_coordinates_cannot_fall_back_to_local_defaults():
    values = {
        "APP_ENV": "production",
        "DATABASE_PORT": 4000,
        "DATABASE_NAME": "synthetic_portal",
        "DATABASE_USER": "synthetic_user",
        "DATABASE_PASSWORD": "synthetic_password",
        "DATABASE_SSL_CA": "/synthetic/tidb-ca.pem",
        "SECRET_KEY": "synthetic-test-signing-key",
        "ADMIN_NAME": "Synthetic Admin",
        "ADMIN_EMAIL": "synthetic-admin@example.test",
        "ADMIN_PASSWORD": "synthetic-admin-password",
    }
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_production_origin_survives_a_render_cors_override():
    settings = make_settings(CORS_ORIGINS=["https://preview.example.test"])

    assert settings.ALLOWED_CORS_ORIGINS.count(PRODUCTION_FRONTEND_ORIGIN) == 1
    assert settings.ALLOWED_CORS_ORIGINS.count(VERCEL_PREVIEW_FRONTEND_ORIGIN) == 1
    assert settings.ALLOWED_CORS_ORIGINS.count(CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN) == 1
    assert "https://preview.example.test" in settings.ALLOWED_CORS_ORIGINS


def test_frontend_origins_preserve_local_and_both_vercel_deployments():
    settings = make_settings()

    assert "http://localhost:5173" in settings.ALLOWED_CORS_ORIGINS
    assert "http://127.0.0.1:3000" in settings.ALLOWED_CORS_ORIGINS
    assert PRODUCTION_FRONTEND_ORIGIN in settings.ALLOWED_CORS_ORIGINS
    assert VERCEL_PREVIEW_FRONTEND_ORIGIN in settings.ALLOWED_CORS_ORIGINS
    assert CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN in settings.ALLOWED_CORS_ORIGINS


def test_cors_preflight_allows_project_preview_origins_for_required_endpoints():
    from starlette.datastructures import Headers
    app = make_cors_asgi_app()

    origins = [
        "https://skill-sphere-career-portal-ab12cd34e-mannat128s-projects.vercel.app",
        "https://skill-sphere-career-portal-ff6otbgaf-mannat128s-projects.vercel.app",
        "https://skill-sphere-career-portal-6c48dtcm6-mannat128s-projects.vercel.app",
    ]
    paths = ["/api/v1/auth/login", "/api/v1/assistant/guest-session"]

    for origin in origins:
        for path in paths:
            response = app.preflight_response(Headers({
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            }))
            assert response.status_code == 200, (origin, path)
            assert response.headers["access-control-allow-origin"] == origin
            assert response.headers["access-control-allow-credentials"] == "true"
            assert "POST" in response.headers["access-control-allow-methods"]
            assert "OPTIONS" in response.headers["access-control-allow-methods"]
            allowed_headers = response.headers["access-control-allow-headers"].lower()
            assert "authorization" in allowed_headers
            assert "content-type" in allowed_headers


def test_cors_preflight_rejects_unrelated_origins():
    from starlette.datastructures import Headers
    app = make_cors_asgi_app()

    origins = [
        "https://different-project-ab12cd34e-mannat128s-projects.vercel.app",
        "https://skill-sphere-career-portal-ab12cd34e-other-team.vercel.app",
        "https://skill-sphere-career-portal-ab12cd34e-mannat128s-projects.vercel.com",
        "http://skill-sphere-career-portal-ab12cd34e-mannat128s-projects.vercel.app",
        "https://skill-sphere-career-portal-.mannat128s-projects.vercel.app",
        "https://skill-sphere-career-portal-ab12cd34e-mannat128s-projects.vercel.app.attacker.test",
    ]

    for origin in origins:
        response = app.preflight_response(Headers({
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }))
        assert response.status_code == 400, origin
        assert "access-control-allow-origin" not in response.headers


def test_fastapi_cors_middleware_uses_anchored_project_regex_and_credentials():
    from pathlib import Path

    main_source = Path(__file__).parents[1] / "app" / "main.py"
    source_text = main_source.read_text(encoding="utf-8")
    assert "allow_origins=settings.ALLOWED_CORS_ORIGINS" in source_text
    assert "allow_origin_regex=VERCEL_PREVIEW_ORIGIN_REGEX" in source_text
    assert "allow_credentials=True" in source_text
    assert "allow_methods=[\"*\"]" in source_text
    assert "allow_headers=[\"*\"]" in source_text


def test_login_origin_is_accepted_by_cors_policy():
    app = make_cors_asgi_app()
    assert app.is_allowed_origin(CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN)
    assert app.allow_credentials is True


def test_development_can_still_use_local_database():
    settings = make_settings(APP_ENV="development", DATABASE_HOST="localhost")

    assert urlsplit(settings.DATABASE_URL).hostname == "localhost"



def test_fastapi_cors_middleware_includes_production_origin():
    from pathlib import Path

    main_source = Path(__file__).parents[1] / "app" / "main.py"
    assert "allow_origins=settings.ALLOWED_CORS_ORIGINS" in main_source.read_text(encoding="utf-8")
    assert PRODUCTION_FRONTEND_ORIGIN in make_settings().ALLOWED_CORS_ORIGINS



def test_blank_app_environment_is_rejected():
    with pytest.raises(ValidationError, match="APP_ENV"):
        make_settings(APP_ENV=" ")


def test_production_requires_explicit_database_ca():
    with pytest.raises(ValidationError, match="DATABASE_SSL_CA"):
        make_settings(DATABASE_SSL_CA=None)


def test_database_driver_enables_ca_and_hostname_verification():
    from app.database.tls import database_engine_options

    settings = make_settings(DATABASE_SSL_CA="/etc/secrets/isrgrootx1.pem")

    assert database_engine_options(settings.DATABASE_SSL_CA) == {
        "connect_args": {
            "ssl_ca": "/etc/secrets/isrgrootx1.pem",
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        }
    }


def test_development_without_ca_keeps_local_connection_options():
    from app.database.tls import database_engine_options

    settings = make_settings(
        APP_ENV="development",
        DATABASE_HOST="localhost",
        DATABASE_SSL_CA=None,
    )

    assert database_engine_options(settings.DATABASE_SSL_CA) == {"connect_args": {}}


def test_alembic_uses_shared_tls_options_without_opening_a_connection():
    from app.database.tls import database_engine_options

    settings = make_settings(DATABASE_SSL_CA="/render-secret/isrgrootx1.pem")
    options = database_engine_options(settings.DATABASE_SSL_CA)

    # These are the exact kwargs passed to Alembic's engine_from_config.
    assert options["connect_args"] == {
        "ssl_ca": "/render-secret/isrgrootx1.pem",
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    }
