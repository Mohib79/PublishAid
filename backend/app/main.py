from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.core.config import settings

app = FastAPI(
    title="PublishAid API",
    description="Backend API for PublishAid academic publishing assistant",
    version="1.0.0",
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


@app.get("/health", tags=["system"], summary="Service health check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
