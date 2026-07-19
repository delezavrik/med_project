"""Тёплый синглтон эмбеддера запросов (BAAI/bge-m3).

Модель большая (~2 ГБ) и грузится один раз. Прогревается в фоне при старте
приложения (см. app/main.py), чтобы первый пользователь не ждал холодную загрузку.
Размерность (1024) и модель должны совпадать с векторами в Qdrant.
"""

from __future__ import annotations

import threading

from app.core.config import get_settings

_lock = threading.Lock()
_model = None
_ready = False


def _load():
    global _model, _ready
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer  # тяжёлый импорт — лениво

            _model = SentenceTransformer(get_settings().embedding_model_name)
            _ready = True
    return _model


def warmup() -> None:
    """Прогрев в фоне: грузит модель и делает пробный проход."""
    try:
        model = _load()
        model.encode("прогрев", normalize_embeddings=True)
    except Exception:  # noqa: BLE001
        pass


def is_ready() -> bool:
    return _ready


def embed(text: str) -> list[float]:
    """Векторизует запрос в нормализованный dense-эмбеддинг (для cosine в Qdrant)."""
    model = _load()
    return model.encode(text, normalize_embeddings=True).tolist()
