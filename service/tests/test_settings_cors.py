from app.core.config import Settings


def test_cors_allowed_origins_defaults_to_dev_frontend() -> None:
    settings = Settings()
    assert settings.cors_allowed_origins == ["http://localhost:5173"]


def test_cors_allowed_origins_parses_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://a.example,http://b.example")
    settings = Settings()
    assert settings.cors_allowed_origins == ["http://a.example", "http://b.example"]


def test_cors_allowed_origins_strips_whitespace_and_empty(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " http://a.example , , http://b.example ")
    settings = Settings()
    assert settings.cors_allowed_origins == ["http://a.example", "http://b.example"]


def test_cors_allowed_origins_accepts_python_list_input() -> None:
    settings = Settings(cors_allowed_origins=["http://x.example", "http://y.example"])
    assert settings.cors_allowed_origins == ["http://x.example", "http://y.example"]


def test_cors_allows_configured_origin(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    from app.core.config import get_settings
    get_settings.cache_clear()

    import sys
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejects_unlisted_origin(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    from app.core.config import get_settings
    get_settings.cache_clear()

    import sys
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "origin": "http://evil.example",
            "access-control-request-method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
