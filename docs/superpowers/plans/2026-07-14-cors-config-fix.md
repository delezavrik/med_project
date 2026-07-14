# CORS Configuration Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the invalid `allow_origins=["*"] + allow_credentials=True` CORS combination with an explicit, settings-driven list of allowed origins. Browsers silently reject the current combination (per CORS spec), so cookies/`Authorization` from cross-origin requests never work today.

**Architecture:** Add a `cors_allowed_origins: list[str]` field to `Settings`, defaulting to the dev frontend origin (`http://localhost:5173`). Parse the env var as comma-separated. In `app/main.py`, pass this list to `CORSMiddleware` — no wildcard when credentials are enabled.

**Tech Stack:** FastAPI 0.115, Starlette CORSMiddleware, pydantic-settings 2.7 (with `field_validator` for comma-splitting since list-typed env parsing is otherwise JSON-encoded).

## Global Constraints

- Do NOT combine `allow_origins=["*"]` with `allow_credentials=True` under any conditions. If a wildcard is genuinely needed (dev only), it must be paired with `allow_credentials=False`.
- Comments and user-facing strings in Russian; identifiers in English.
- Keep existing dev workflow working out-of-the-box: `docker compose -f docker-compose.dev.yml up` must not require additional env config to make the frontend at `http://localhost:5173` talk to the backend.

---

### Task 1: Add cors_allowed_origins setting with test

**Files:**
- Modify: `service/backend/app/core/config.py`
- Create: `service/tests/test_settings_cors.py`
- Modify: `service/backend/.env.docker.example`
- Modify: `service/backend/.env.example`

**Interfaces:**
- Consumes: nothing (starting point).
- Produces: `Settings.cors_allowed_origins: list[str]` — comma-separated env var `CORS_ALLOWED_ORIGINS`; default `["http://localhost:5173"]`. Whitespace around entries trimmed; empty entries dropped.

- [ ] **Step 1: Write the failing test**

Create `service/tests/test_settings_cors.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd service && pytest tests/test_settings_cors.py -v
```

Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'cors_allowed_origins'`.

- [ ] **Step 3: Add the setting and a comma-splitting validator (additive edit)**

**IMPORTANT:** This is an additive edit. Do NOT overwrite the whole file — other fields (including pool settings from the Postgres pool plan, if it has landed) must be preserved. Use `Edit`, not `Write`.

In `service/backend/app/core/config.py`:

(a) Add the `field_validator` import. Change:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
```

to:

```python
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
```

(b) Add the field to `Settings`. Immediately before the `model_config = SettingsConfigDict(...)` line, insert:

```python
    cors_allowed_origins: list[str] = ["http://localhost:5173"]

```

(c) Add the validator inside the `Settings` class body, immediately after the `model_config = SettingsConfigDict(...)` block:

```python
    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        # Env vars приходят строкой; поддерживаем формат "a,b, c".
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
```

Verify with:

```bash
cd service && grep -c "cors_allowed_origins" backend/app/core/config.py
```

Expected: `2` (one field, one validator). If the pool plan has already landed, `grep postgres_pool backend/app/core/config.py` should still return non-empty — you did not delete pool fields.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd service && pytest tests/test_settings_cors.py -v
```

Expected: all four tests PASS.

- [ ] **Step 5: Document the env var**

Append to `service/backend/.env.docker.example` after line 3 (`API_PREFIX="/api/v1"`):

```
# Разрешённые origins для CORS. Comma-separated. Пусто = только backend без cross-origin запросов.
CORS_ALLOWED_ORIGINS="http://localhost:5173"
```

Add the same two lines to `service/backend/.env.example`.

- [ ] **Step 6: Commit**

```bash
git add service/backend/app/core/config.py service/tests/test_settings_cors.py service/backend/.env.docker.example service/backend/.env.example
git commit -m "feat(config): add CORS_ALLOWED_ORIGINS setting with comma-separated parsing"
```

---

### Task 2: Replace wildcard CORS config in main.py

**Files:**
- Modify: `service/backend/app/main.py`

**Interfaces:**
- Consumes: `settings.cors_allowed_origins` from Task 1.
- Produces: `CORSMiddleware` configured with `allow_origins=settings.cors_allowed_origins` and `allow_credentials=True`. No wildcard.

- [ ] **Step 1: Replace the CORSMiddleware block**

In `service/backend/app/main.py`, replace lines 12-18:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для MVP. В production указать домен сайта.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

with:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Verify no wildcard combo remains**

```bash
cd service && grep -n 'allow_origins' backend/app/main.py
```

Expected: single line `allow_origins=settings.cors_allowed_origins,`.

- [ ] **Step 3: Add CORS behavior test**

Append to `service/tests/test_settings_cors.py`:

```python
from fastapi.testclient import TestClient


def test_cors_allows_configured_origin(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.main import app
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

    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.main import app
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "origin": "http://evil.example",
            "access-control-request-method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
```

- [ ] **Step 4: Run the new tests**

```bash
cd service && pytest tests/test_settings_cors.py -v
```

Expected: all six tests PASS.

Note: `TestClient(app)` will call the lifespan. If the pool-plan lifespan (see `2026-07-14-postgres-connection-pool.md`) is in place and Postgres isn't available in the test env, the lifespan should still succeed — `create_pool` returns `None` when `POSTGRES_DSN` is unset in the test env. If tests hit a real DSN in the test env, prefix them with `monkeypatch.delenv("POSTGRES_DSN", raising=False)`.

- [ ] **Step 5: Verify browser-flow smoke in Docker**

```bash
cd service && docker compose -f docker-compose.dev.yml up -d --build backend
sleep 5
curl -si -X OPTIONS http://localhost:8000/api/v1/facets \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin"
```

Expected: response includes `access-control-allow-origin: http://localhost:5173` (not `*`).

```bash
curl -si -X OPTIONS http://localhost:8000/api/v1/facets \
  -H "Origin: http://evil.example" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin"
```

Expected: no `access-control-allow-origin` header (or the header is absent from response).

- [ ] **Step 6: Open the frontend and verify the UI still loads data**

```bash
open http://localhost:5173
```

Manual check: dashboard renders, `/api/v1/facets` returns 200, no CORS error in browser devtools console.

- [ ] **Step 7: Commit**

```bash
git add service/backend/app/main.py service/tests/test_settings_cors.py
git commit -m "fix(cors): replace wildcard with explicit origin list to make credentials-mode valid"
```
