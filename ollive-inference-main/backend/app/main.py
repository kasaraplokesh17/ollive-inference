from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
import structlog

from app.core.config import settings
from app.db.database import init_db
from app.db.redis_client import init_redis, close_redis
from app.services.pii_service import init_pii_engine
from app.api.routes import chat, conversations, ingest, metrics

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Ollive Inference API")
    await init_db()
    await init_redis()
    init_pii_engine()
    logger.info("Startup complete")
    yield
    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Ollive Inference API",
    description="LLM inference logging, ingestion, and observability",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-ID"],
)

# Prometheus instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics/prometheus")

# Routes
app.include_router(chat.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ollive-inference-api"}


@app.get("/")
async def root():
    return {"message": "Ollive Inference API", "docs": "/docs"}
