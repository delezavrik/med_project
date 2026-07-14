from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.db import create_pool, get_pool, set_pool

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool(settings)
    set_pool(pool)
    try:
        if pool is not None:
            pool.open(wait=True, timeout=settings.postgres_pool_timeout)
        yield
    finally:
        current = get_pool()
        set_pool(None)
        if current is not None:
            current.close()


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
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


app.include_router(api_router, prefix=settings.api_prefix)
