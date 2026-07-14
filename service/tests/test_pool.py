from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.core.db import create_pool, get_pool, set_pool


def test_create_pool_returns_none_when_dsn_missing() -> None:
    settings = Settings(postgres_dsn=None)
    assert create_pool(settings) is None


def test_create_pool_uses_configured_sizes() -> None:
    settings = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/db",
        postgres_pool_min_size=3,
        postgres_pool_max_size=7,
        postgres_pool_timeout=12.0,
    )
    pool = create_pool(settings)
    try:
        assert isinstance(pool, ConnectionPool)
        assert pool.min_size == 3
        assert pool.max_size == 7
        assert pool.timeout == 12.0
    finally:
        if pool is not None:
            pool.close()


def test_get_pool_reflects_set_pool() -> None:
    set_pool(None)
    assert get_pool() is None

    settings = Settings(postgres_dsn="postgresql://user:pass@localhost:5432/db")
    pool = create_pool(settings)
    try:
        set_pool(pool)
        assert get_pool() is pool
    finally:
        set_pool(None)
        if pool is not None:
            pool.close()
