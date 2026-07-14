from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import Settings


_pool: ConnectionPool | None = None


def create_pool(settings: Settings) -> ConnectionPool | None:
    """Создаёт (но не открывает) pool. Возвращает None, если DSN не задан."""
    if not settings.postgres_dsn:
        return None
    return ConnectionPool(
        conninfo=settings.postgres_dsn,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        timeout=settings.postgres_pool_timeout,
        kwargs={"row_factory": dict_row},
        open=False,
    )


def set_pool(pool: ConnectionPool | None) -> None:
    global _pool
    _pool = pool


def get_pool() -> ConnectionPool | None:
    return _pool
