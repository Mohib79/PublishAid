import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.journals import router as journals_router
from app.api.projects import router as projects_router
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.services.embedding import init_embedder
        init_embedder()
    except Exception as e:
        logger.warning(f"Could not warm up embedding model at startup: {e}")
    yield


app = FastAPI(
    title="PublishAid API",
    description="Backend API for PublishAid academic publishing assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS Middleware per specification
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_headers=["Authorization", "Content-Type"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)

# Include Authentication Router
app.include_router(auth_router)
app.include_router(journals_router)
app.include_router(journals_router, prefix="/api")
app.include_router(projects_router)
app.include_router(projects_router, prefix="/api")


@app.get("/health", tags=["system"], summary="Service health check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
