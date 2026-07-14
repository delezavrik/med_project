# BGE-M3 Embedding Model Warmup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the multi-second cold-start latency on the first RAG-triggering request by loading the BGE-M3 embedding model at FastAPI startup (via lifespan) instead of lazily inside `QdrantTool._embed` on first call. Also make the model a real singleton — right now `ToolRouter.__init__` creates a fresh `QdrantTool` per request, so even the current lazy-load is per-instance rather than per-process.

**Architecture:**
- New module `app/core/embeddings.py` owns a process-wide `Embedder` protocol and a `BgeM3Embedder` concrete class. It exposes `set_embedder`/`get_embedder` (mirroring the pool pattern in `app/core/db.py`).
- FastAPI `lifespan` in `app/main.py` calls `BgeM3Embedder.load(...)` when `EMBEDDING_PROVIDER=bge_m3` and `EMBEDDING_WARMUP=true` (new setting). On failure it logs a warning and leaves the embedder unset — RAG requests then fall back to today's error path.
- `QdrantTool._embed` uses `get_embedder()` instead of its per-instance `self._bge_model`. If no embedder is set (warmup off or provider is OpenAI), it falls back to the current behaviour (lazy import or OpenAI API path).
- Docker `Dockerfile` gains a build-time model prefetch step so the HuggingFace snapshot is baked into the image (removing HF-hub download from cold start entirely). HF cache dir points to `/root/.cache/huggingface` (default).
- `/health` endpoint gains an optional `embedding` block reporting whether warmup succeeded.

**Tech Stack:** Python 3.11, FastAPI lifespan, `FlagEmbedding>=1.3.4` (already in requirements), HuggingFace Hub for model download at build time.

## Global Constraints

- Warmup **must be opt-in** via `EMBEDDING_WARMUP=true` so local dev without GPU/large RAM isn't blocked from `docker compose up`. Default: `false`.
- BGE-M3 model must be `BAAI/bge-m3` (dim=1024). Under no circumstance may the loaded model change to something with a different dim — Qdrant collection is size-locked to 1024.
- If warmup fails, the app must still start (log the error, continue) — RAG endpoints will surface the same error as today.
- Comments and user-facing strings in Russian; identifiers in English.
- Do not touch offline scripts (`app/offline/build_qdrant_index.py`) — this plan only affects the request-path embedder.

---

### Task 1: Add embeddings module with tests

**Files:**
- Create: `service/backend/app/core/embeddings.py`
- Create: `service/tests/test_embeddings.py`

**Interfaces:**
- Consumes: `Settings` (`embedding_provider`, `embedding_model_name`, `embedding_warmup`).
- Produces:
  - `Embedder` protocol with method `embed(text: str) -> list[float]`.
  - `BgeM3Embedder(Embedder)` — wraps `FlagEmbedding.BGEM3FlagModel`. `load(model_name: str) -> BgeM3Embedder` classmethod.
  - Module-level `set_embedder(embedder: Embedder | None) -> None`.
  - Module-level `get_embedder() -> Embedder | None`.

- [ ] **Step 1: Write the failing test**

Create `service/tests/test_embeddings.py`:

```python
from app.core import embeddings


class _FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        return [float(len(text))]


def test_get_embedder_defaults_to_none() -> None:
    embeddings.set_embedder(None)
    assert embeddings.get_embedder() is None


def test_set_and_get_embedder_roundtrip() -> None:
    fake = _FakeEmbedder()
    embeddings.set_embedder(fake)
    try:
        assert embeddings.get_embedder() is fake
        assert embeddings.get_embedder().embed("abc") == [3.0]
    finally:
        embeddings.set_embedder(None)


def test_bge_m3_embedder_encode_delegates_to_underlying_model() -> None:
    import numpy as np

    class _StubModel:
        def encode(self, texts, **kwargs):
            return {"dense_vecs": np.asarray([[0.1, 0.2, 0.3]], dtype="float32")}

    e = embeddings.BgeM3Embedder(_StubModel())
    assert e.embed("hi") == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd service && pytest tests/test_embeddings.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.embeddings'`.

- [ ] **Step 3: Implement embeddings module**

Create `service/backend/app/core/embeddings.py`:

```python
"""Process-wide синглтон embedder для BGE-M3 (или совместимой модели).

Модель тяжёлая; создаётся один раз при старте FastAPI через lifespan.
Если warmup отключён или упал, `get_embedder()` возвращает None и
`QdrantTool._embed` идёт по старому пути (lazy import).
"""

from typing import Protocol


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class BgeM3Embedder:
    def __init__(self, model) -> None:
        self._model = model

    @classmethod
    def load(cls, model_name: str, *, use_fp16: bool = False) -> "BgeM3Embedder":
        # Импорт локальный: FlagEmbedding очень тяжёлый по времени старта
        # и не нужен, если warmup отключён.
        from FlagEmbedding import BGEM3FlagModel

        model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
        return cls(model)

    def embed(self, text: str) -> list[float]:
        encoded = self._model.encode(
            [text],
            batch_size=1,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return encoded["dense_vecs"][0].astype("float32").tolist()


_embedder: Embedder | None = None


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder
    _embedder = embedder


def get_embedder() -> Embedder | None:
    return _embedder
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd service && pytest tests/test_embeddings.py -v
```

Expected: three tests PASS (the third only if numpy is installed; it is per `requirements.txt` line 10).

- [ ] **Step 5: Commit**

```bash
git add service/backend/app/core/embeddings.py service/tests/test_embeddings.py
git commit -m "feat(embeddings): add process-wide Embedder singleton with BGE-M3 impl"
```

---

### Task 2: Add embedding_warmup setting

**Files:**
- Modify: `service/backend/app/core/config.py`
- Modify: `service/backend/.env.docker.example`
- Modify: `service/backend/.env.example`

**Interfaces:**
- Consumes: nothing (starting point).
- Produces: `Settings.embedding_warmup: bool = False`. Env var `EMBEDDING_WARMUP` (accepts `"true"`/`"false"` via pydantic's built-in bool coercion).

- [ ] **Step 1: Add setting**

In `service/backend/app/core/config.py`, add after `embedding_model_name: str = "BAAI/bge-m3"`:

```python
    embedding_warmup: bool = False
```

- [ ] **Step 2: Document env var**

Append to `service/backend/.env.docker.example` after `EMBEDDING_MODEL_NAME="BAAI/bge-m3"`:

```
# Загружать embedding-модель в момент старта FastAPI (устраняет холодный первый RAG-запрос).
# Требует ~2 ГБ RAM для BAAI/bge-m3. Для локальной разработки без RAG оставь false.
EMBEDDING_WARMUP="false"
```

Add the same to `service/backend/.env.example`.

- [ ] **Step 3: Commit**

```bash
git add service/backend/app/core/config.py service/backend/.env.docker.example service/backend/.env.example
git commit -m "feat(config): add EMBEDDING_WARMUP flag (default false)"
```

---

### Task 3: Wire embedder warmup into lifespan and update /health

**Files:**
- Modify: `service/backend/app/main.py`

**Interfaces:**
- Consumes: `BgeM3Embedder.load`, `set_embedder`, `get_embedder` from `app.core.embeddings`; `settings.embedding_warmup`, `settings.embedding_provider`, `settings.embedding_model_name`.
- Produces: `lifespan` context manager that loads the embedder on startup when `embedding_warmup=True` and `embedding_provider=="bge_m3"`. `/health` returns `embedding: {"warmup": bool, "loaded": bool, "error": str | None}`.

**Note:** If the postgres-pool plan (`2026-07-14-postgres-connection-pool.md`) has been applied, `lifespan` already exists — extend it. If not, create it.

- [ ] **Step 1: Replace / extend main.py**

Replace `service/backend/app/main.py` with (this version assumes the pool plan is applied; adapt trivially if not):

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.db import create_pool, get_pool, set_pool
from app.core.embeddings import BgeM3Embedder, get_embedder, set_embedder
from app.ui import router as ui_router

logger = logging.getLogger(__name__)

settings = get_settings()

_embedding_status: dict = {"warmup": False, "loaded": False, "error": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool(settings)
    if pool is not None:
        pool.open(wait=True)
    set_pool(pool)

    _embedding_status["warmup"] = bool(settings.embedding_warmup)
    if settings.embedding_warmup and settings.embedding_provider == "bge_m3":
        try:
            embedder = BgeM3Embedder.load(settings.embedding_model_name)
            set_embedder(embedder)
            _embedding_status["loaded"] = True
        except Exception as exc:  # noqa: BLE001
            _embedding_status["error"] = f"{type(exc).__name__}: {exc}"
            logger.exception("BGE-M3 warmup failed; RAG requests will retry lazily.")

    try:
        yield
    finally:
        current_pool = get_pool()
        set_pool(None)
        if current_pool is not None:
            current_pool.close()

        set_embedder(None)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "embedding": {
            **_embedding_status,
            "provider": settings.embedding_provider,
            "model": settings.embedding_model_name,
        },
    }


app.include_router(ui_router)
app.include_router(api_router, prefix=settings.api_prefix)
```

- [ ] **Step 2: Add lifespan test**

Create `service/tests/test_lifespan_embedder.py`:

```python
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_shows_warmup_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_WARMUP", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.main import app
    with TestClient(app) as client:
        r = client.get("/health")
        body = r.json()
        assert body["embedding"]["warmup"] is False
        assert body["embedding"]["loaded"] is False


def test_health_shows_loaded_when_warmup_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_WARMUP", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "bge_m3")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    from app.core.config import get_settings
    get_settings.cache_clear()

    class _Stub:
        def embed(self, text: str) -> list[float]:
            return [0.0]

    with patch("app.core.embeddings.BgeM3Embedder.load", return_value=_Stub()):
        from app.main import app
        with TestClient(app) as client:
            r = client.get("/health")
            body = r.json()
            assert body["embedding"]["warmup"] is True
            assert body["embedding"]["loaded"] is True


def test_health_reports_error_when_warmup_fails(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_WARMUP", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "bge_m3")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    from app.core.config import get_settings
    get_settings.cache_clear()

    with patch(
        "app.core.embeddings.BgeM3Embedder.load",
        side_effect=RuntimeError("no GPU"),
    ):
        from app.main import app
        with TestClient(app) as client:
            r = client.get("/health")
            body = r.json()
            assert body["embedding"]["loaded"] is False
            assert body["embedding"]["error"] is not None
            assert "RuntimeError" in body["embedding"]["error"]
```

- [ ] **Step 3: Run tests**

```bash
cd service && pytest tests/test_lifespan_embedder.py -v
```

Expected: all three tests PASS.

- [ ] **Step 4: Commit**

```bash
git add service/backend/app/main.py service/tests/test_lifespan_embedder.py
git commit -m "feat(app): warmup BGE-M3 in lifespan and expose status in /health"
```

---

### Task 4: Wire QdrantTool through the singleton embedder

**Files:**
- Modify: `service/backend/app/tools/qdrant_tool.py`
- Create: `service/tests/test_qdrant_tool_embedder.py`

**Interfaces:**
- Consumes: `get_embedder()` from `app.core.embeddings`.
- Produces: `QdrantTool._embed` uses the process-wide embedder when available; falls back to lazy `BGEM3FlagModel(...)` (as today) if not. `self._bge_model` remains for the fallback path so multiple QdrantTool instances still share the fallback model per-instance (existing behaviour).

- [ ] **Step 1: Write the failing test**

Create `service/tests/test_qdrant_tool_embedder.py`:

```python
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core import embeddings


def test_qdrant_tool_uses_process_embedder_when_available(monkeypatch) -> None:
    from app.tools.qdrant_tool import QdrantTool

    stub = MagicMock()
    stub.embed.return_value = [0.1] * 1024
    embeddings.set_embedder(stub)

    try:
        tool = QdrantTool()
        tool.settings = SimpleNamespace(
            embedding_provider="bge_m3",
            embedding_model_name="BAAI/bge-m3",
            openai_api_key=None,
            openai_embedding_model="",
        )

        result = tool._embed("some query text")  # noqa: SLF001

        stub.embed.assert_called_once_with("some query text")
        assert result == [0.1] * 1024
    finally:
        embeddings.set_embedder(None)


def test_qdrant_tool_falls_back_to_lazy_load_when_no_embedder(monkeypatch) -> None:
    embeddings.set_embedder(None)

    from app.tools import qdrant_tool as qt_module

    fake_encoded = {"dense_vecs": __import__("numpy").asarray([[0.5] * 1024], dtype="float32")}

    class _FakeModel:
        def encode(self, *args, **kwargs):
            return fake_encoded

    class _FakeFlagEmbedding:
        BGEM3FlagModel = staticmethod(lambda name, use_fp16=False: _FakeModel())

    monkeypatch.setitem(__import__("sys").modules, "FlagEmbedding", _FakeFlagEmbedding)

    tool = qt_module.QdrantTool()
    tool.settings = SimpleNamespace(
        embedding_provider="bge_m3",
        embedding_model_name="BAAI/bge-m3",
        openai_api_key=None,
        openai_embedding_model="",
    )

    result = tool._embed("hello")  # noqa: SLF001
    assert result == [0.5] * 1024
    assert tool._bge_model is not None  # noqa: SLF001 — fallback did lazy-load
```

- [ ] **Step 2: Run test to verify first assertion fails**

```bash
cd service && pytest tests/test_qdrant_tool_embedder.py::test_qdrant_tool_uses_process_embedder_when_available -v
```

Expected: FAIL — current `_embed` never consults `get_embedder()`, so `stub.embed` is not called.

- [ ] **Step 3: Update _embed to prefer the singleton**

In `service/backend/app/tools/qdrant_tool.py`, add import at the top:

```python
from app.core.embeddings import get_embedder
```

Replace the `_embed` method body (lines 90-130 in the current file) with:

```python
    def _embed(self, text: str) -> list[float]:
        """Строит embedding для semantic search.

        Приоритет:
        1. Process-wide embedder, загруженный в lifespan (EMBEDDING_WARMUP=true).
        2. Ленивая загрузка BGE-M3 при первом вызове (текущее поведение).
        3. OpenAI embeddings API — если EMBEDDING_PROVIDER != bge_m3.
        """
        if self.settings.embedding_provider == "bge_m3":
            embedder = get_embedder()
            if embedder is not None:
                return embedder.embed(text)

            try:
                from FlagEmbedding import BGEM3FlagModel
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "EMBEDDING_PROVIDER=bge_m3, но пакет FlagEmbedding недоступен. "
                    "Пересобери Docker image backend."
                ) from exc

            if self._bge_model is None:
                self._bge_model = BGEM3FlagModel(self.settings.embedding_model_name, use_fp16=False)

            encoded = self._bge_model.encode(
                [text],
                batch_size=1,
                max_length=8192,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            return encoded["dense_vecs"][0].astype("float32").tolist()

        if not self.settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY не задан. Для RAG-поиска через Qdrant нужен embedding API "
                "или локальный encoder с той же размерностью, что и коллекция."
            )

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=text,
        )
        return list(response.data[0].embedding)
```

- [ ] **Step 4: Run both tests**

```bash
cd service && pytest tests/test_qdrant_tool_embedder.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add service/backend/app/tools/qdrant_tool.py service/tests/test_qdrant_tool_embedder.py
git commit -m "refactor(qdrant-tool): use process-wide embedder when warmup is enabled"
```

---

### Task 5: Pre-bake the model into the Docker image

**Files:**
- Modify: `service/backend/Dockerfile`

**Interfaces:**
- Consumes: `FlagEmbedding` package installed via requirements.
- Produces: Docker image with `BAAI/bge-m3` snapshot cached under `/root/.cache/huggingface/hub/` at build time. Avoids the first-run HuggingFace download (~2 GB) inside the running container.

- [ ] **Step 1: Modify Dockerfile**

Replace `service/backend/Dockerfile` with:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Прогреваем HuggingFace cache: скачиваем BAAI/bge-m3 в образ, чтобы холодный
# старт контейнера не тянул ~2 ГБ модели из интернета.
ARG EMBEDDING_MODEL_NAME=BAAI/bge-m3
ARG PREFETCH_EMBEDDING_MODEL=true
RUN if [ "$PREFETCH_EMBEDDING_MODEL" = "true" ]; then \
      python -c "from huggingface_hub import snapshot_download; snapshot_download('${EMBEDDING_MODEL_NAME}')"; \
    fi

COPY app ./app
```

- [ ] **Step 2: Rebuild backend and time the RAG cold start**

```bash
cd service
time docker compose -f docker-compose.dev.yml build backend
```

Expected: build succeeds; the snapshot download step adds ~1-3 minutes to build (one-time). Repeat builds hit the layer cache.

- [ ] **Step 3: Start the stack with warmup ON and verify /health**

```bash
cd service
# Set warmup ON in the local env
grep -q '^EMBEDDING_WARMUP=' backend/.env && \
  sed -i.bak 's/^EMBEDDING_WARMUP=.*/EMBEDDING_WARMUP="true"/' backend/.env || \
  echo 'EMBEDDING_WARMUP="true"' >> backend/.env

docker compose -f docker-compose.dev.yml up -d
sleep 20  # BGE-M3 CPU load takes ~10-15s from prewarmed HF cache
curl -sf http://localhost:8000/health
```

Expected: JSON response with `embedding.loaded == true`.

- [ ] **Step 4: Measure first-RAG-request latency**

With warmup ON, the first request that hits Qdrant should NOT pay the model-load cost:

```bash
time curl -sf -X POST http://localhost:8000/api/v1/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"message":"похожие отзывы про доставку"}' > /dev/null
```

Expected: total time < 3 s (embedding is single-request through the pre-loaded model; assuming Qdrant/DB are reachable). Compare with `EMBEDDING_WARMUP=false` restart — the first request there will be much slower.

- [ ] **Step 5: Commit**

```bash
git add service/backend/Dockerfile
git commit -m "build(backend): pre-fetch BAAI/bge-m3 snapshot into Docker image"
```

---

### Task 6: Document the tradeoff and safe defaults

**Files:**
- Modify: `service/README.md` (or `README_LOCAL_DB.md` — whichever documents startup) — add a short "Embedding warmup" section.

**Interfaces:**
- Consumes: nothing.
- Produces: one short paragraph explaining what `EMBEDDING_WARMUP=true` does, when to enable it (production, load testing), and the RAM cost (~2 GB resident for BAAI/bge-m3 on CPU).

- [ ] **Step 1: Locate the right README section**

```bash
cd service && grep -n "docker compose" README.md README_LOCAL_DB.md 2>/dev/null | head
```

Add the section to whichever file already documents the "how to run" flow.

- [ ] **Step 2: Insert warmup section**

Add a subsection titled `### Embedding warmup` under the "Running / Env vars" section, with content:

```markdown
### Embedding warmup

По умолчанию BGE-M3 загружается **лениво** при первом RAG-запросе: это удобно для локальной разработки (быстрый старт),
но первый чат-запрос платит ~10-15 сек на CPU-инференс + вес модели ~2 ГБ.

В продакшне выставь `EMBEDDING_WARMUP=true` в `.env`. При этом:

- модель `BAAI/bge-m3` загружается один раз при старте FastAPI (в lifespan);
- статус доступен на `/health` в поле `embedding.loaded`;
- если загрузка упала — приложение всё равно поднимется (ошибка в `embedding.error`), а RAG-запросы вернутся к ленивому пути;
- контейнеру нужно ~2 ГБ RAM с запасом.
```

- [ ] **Step 3: Commit**

```bash
git add service/README.md service/README_LOCAL_DB.md 2>/dev/null
git commit -m "docs: document EMBEDDING_WARMUP tradeoff and RAM cost"
```
