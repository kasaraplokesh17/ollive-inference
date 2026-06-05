from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import structlog

from app.db.database import get_db
from app.services.ingestion import process_log, enqueue_log

router = APIRouter(prefix="/ingest", tags=["ingestion"])
logger = structlog.get_logger()


class LogPayload(BaseModel):
    provider: str
    model: str
    request_timestamp: str
    response_timestamp: Optional[str] = None
    conversation_id: Optional[str] = None
    latency_ms: Optional[float] = None
    time_to_first_token_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    status: Optional[str] = "success"
    error_message: Optional[str] = None
    is_streaming: Optional[bool] = False
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    extra: Optional[dict] = {}


@router.post("/log")
async def ingest_log(
    payload: LogPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingestion endpoint: receives inference logs from SDK.
    Validates, stores in DB, and publishes to Redis event bus.
    """
    data = payload.model_dump()

    # Store in DB
    log = await process_log(data, db)
    if not log:
        raise HTTPException(422, "Invalid log payload")

    # Publish to event bus (async, non-blocking)
    background_tasks.add_task(enqueue_log, data)

    return {"status": "accepted", "log_id": str(log.id)}


@router.get("/stats")
async def ingest_stats(db: AsyncSession = Depends(get_db)):
    """Quick stats for health checking the pipeline."""
    from sqlalchemy import func, select
    from app.models.inference_log import InferenceLog
    from datetime import datetime, timezone, timedelta

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(
            func.count(InferenceLog.id).label("total"),
            func.avg(InferenceLog.latency_ms).label("avg_latency"),
            func.sum(InferenceLog.total_tokens).label("total_tokens"),
        ).where(InferenceLog.created_at >= since)
    )
    row = result.one()
    return {
        "last_24h": {
            "total_logs": row.total or 0,
            "avg_latency_ms": round(row.avg_latency or 0, 2),
            "total_tokens": row.total_tokens or 0,
        }
    }
