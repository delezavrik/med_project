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
