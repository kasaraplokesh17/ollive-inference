from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, text
from datetime import datetime, timezone, timedelta
import structlog

from app.db.database import get_db
from app.models.inference_log import InferenceLog, RequestStatus

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = structlog.get_logger()


@router.get("/overview")
async def metrics_overview(hours: int = 24, db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Total requests, errors, latency
    result = await db.execute(
        select(
            func.count(InferenceLog.id).label("total"),
            func.avg(InferenceLog.latency_ms).label("avg_latency"),
            func.min(InferenceLog.latency_ms).label("min_latency"),
            func.max(InferenceLog.latency_ms).label("max_latency"),
            func.sum(InferenceLog.total_tokens).label("total_tokens"),
            func.avg(InferenceLog.time_to_first_token_ms).label("avg_ttft"),
        ).where(InferenceLog.created_at >= since)
    )
    row = result.one()

    error_result = await db.execute(
        select(func.count(InferenceLog.id))
        .where(InferenceLog.created_at >= since)
        .where(InferenceLog.status == RequestStatus.error)
    )
    error_count = error_result.scalar() or 0
    total = row.total or 1

    return {
        "period_hours": hours,
        "total_requests": row.total or 0,
        "error_count": error_count,
        "error_rate": round(error_count / total * 100, 2),
        "avg_latency_ms": round(row.avg_latency or 0, 2),
        "min_latency_ms": round(row.min_latency or 0, 2),
        "max_latency_ms": round(row.max_latency or 0, 2),
        "avg_ttft_ms": round(row.avg_ttft or 0, 2),
        "total_tokens": row.total_tokens or 0,
    }


@router.get("/by-provider")
async def metrics_by_provider(hours: int = 24, db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(
            InferenceLog.provider,
            InferenceLog.model,
            func.count(InferenceLog.id).label("count"),
            func.avg(InferenceLog.latency_ms).label("avg_latency"),
            func.sum(InferenceLog.total_tokens).label("tokens"),
        )
        .where(InferenceLog.created_at >= since)
        .group_by(InferenceLog.provider, InferenceLog.model)
        .order_by(func.count(InferenceLog.id).desc())
    )
    rows = result.all()
    return {
        "providers": [
            {
                "provider": r.provider,
                "model": r.model,
                "request_count": r.count,
                "avg_latency_ms": round(r.avg_latency or 0, 2),
                "total_tokens": r.tokens or 0,
            }
            for r in rows
        ]
    }


@router.get("/latency-histogram")
async def latency_histogram(hours: int = 24, db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(InferenceLog.latency_ms)
        .where(InferenceLog.created_at >= since)
        .where(InferenceLog.latency_ms.isnot(None))
    )
    latencies = [r[0] for r in result.all()]

    buckets = [0, 100, 250, 500, 1000, 2000, 5000, float("inf")]
    labels = ["<100ms", "100-250ms", "250-500ms", "500ms-1s", "1-2s", "2-5s", ">5s"]
    counts = [0] * len(labels)

    for lat in latencies:
        for i in range(len(buckets) - 1):
            if buckets[i] <= lat < buckets[i + 1]:
                counts[i] += 1
                break

    return {"buckets": [{"label": l, "count": c} for l, c in zip(labels, counts)]}


@router.get("/timeseries")
async def timeseries(hours: int = 24, db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(
            func.date_trunc("hour", InferenceLog.created_at).label("hour"),
            func.count(InferenceLog.id).label("count"),
            func.avg(InferenceLog.latency_ms).label("avg_latency"),
        )
        .where(InferenceLog.created_at >= since)
        .group_by(text("hour"))
        .order_by(text("hour"))
    )
    rows = result.all()
    return {
        "timeseries": [
            {
                "hour": r.hour.isoformat() if r.hour else None,
                "request_count": r.count,
                "avg_latency_ms": round(r.avg_latency or 0, 2),
            }
            for r in rows
        ]
    }


@router.get("/recent-logs")
async def recent_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InferenceLog)
        .order_by(InferenceLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id": str(l.id),
                "provider": l.provider,
                "model": l.model,
                "latency_ms": l.latency_ms,
                "total_tokens": l.total_tokens,
                "status": l.status.value,
                "is_streaming": l.is_streaming,
                "created_at": l.created_at.isoformat(),
                "input_preview": l.input_preview,
                "output_preview": l.output_preview,
            }
            for l in logs
        ]
    }
