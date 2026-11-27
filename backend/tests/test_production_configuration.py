from urllib.parse import urlsplit

import pytest
from pydantic import ValidationError

from app.core.config import (
    CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN,
    PRODUCTION_FRONTEND_ORIGIN,
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


@pytest.mark.parametrize(
    "path",
    ["/api/v1/auth/login", "/api/v1/assistant/guest-session"],
)
def test_cors_preflight_allows_current_preview_origin_for_api_post(path):
    import asyncio

    import httpx
    from app.main import app

    async def send_preflight():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.options(
                path,
                headers={
                    "Origin": CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )

    response = asyncio.run(send_preflight())
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "OPTIONS" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


def test_login_returns_cors_headers_for_preview_origin_with_invalid_credentials():
    import asyncio

    import httpx
    from app.main import app
    from app.database.session import get_db
    from app.models.user import User
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(test_engine)
    test_session_factory = sessionmaker(bind=test_engine)

    def override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    async def send_login():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/auth/login",
                json={"email": "missing-user@example.com", "password": "synthetic-invalid"},
                headers={"Origin": CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN},
            )

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = asyncio.run(send_login())
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        test_engine.dispose()

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == CURRENT_VERCEL_PREVIEW_FRONTEND_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_development_can_still_use_local_database():
    settings = make_settings(APP_ENV="development", DATABASE_HOST="localhost")

    assert urlsplit(settings.DATABASE_URL).hostname == "localhost"



def test_fastapi_cors_middleware_includes_production_origin():
    from app.main import app

    cors = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )
    assert PRODUCTION_FRONTEND_ORIGIN in cors.kwargs["allow_origins"]



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
