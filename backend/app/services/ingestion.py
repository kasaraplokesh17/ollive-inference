"""
Ingestion pipeline: receives SDK logs, validates, stores, and queues for async processing.
Uses Redis pub/sub for event-based architecture.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inference_log import InferenceLog, RequestStatus
from app.db.redis_client import get_redis

logger = structlog.get_logger()

INGEST_CHANNEL = "ollive:ingest"
INGEST_QUEUE = "ollive:ingest:queue"


class IngestPayload:
    """Validates and parses inbound log payloads from SDK."""

    REQUIRED_FIELDS = {"provider", "model", "request_timestamp"}

    def __init__(self, data: dict):
        self.raw = data
        self.errors: list[str] = []
        self._validate()

    def _validate(self):
        for field in self.REQUIRED_FIELDS:
            if field not in self.raw or not self.raw[field]:
                self.errors.append(f"Missing required field: {field}")

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_log(self, conversation_id: Optional[str] = None) -> dict:
        return {
            "conversation_id": conversation_id or self.raw.get("conversation_id"),
            "provider": self.raw.get("provider"),
            "model": self.raw.get("model"),
            "request_timestamp": self.raw.get("request_timestamp"),
            "response_timestamp": self.raw.get("response_timestamp"),
            "latency_ms": self.raw.get("latency_ms"),
            "time_to_first_token_ms": self.raw.get("time_to_first_token_ms"),
            "prompt_tokens": self.raw.get("prompt_tokens"),
            "completion_tokens": self.raw.get("completion_tokens"),
            "total_tokens": self.raw.get("total_tokens"),
            "status": self.raw.get("status", "success"),
            "error_message": self.raw.get("error_message"),
            "is_streaming": self.raw.get("is_streaming", False),
            "input_preview": self.raw.get("input_preview"),
            "output_preview": self.raw.get("output_preview"),
            "extra_metadata": self.raw.get("extra", {}),
        }


async def enqueue_log(payload: dict):
    """Push log to Redis queue for async processing."""
    redis = await get_redis()
    if redis:
        await redis.lpush(INGEST_QUEUE, json.dumps(payload))
        await redis.publish(INGEST_CHANNEL, json.dumps({"type": "new_log"}))


async def process_log(data: dict, db: AsyncSession) -> Optional[InferenceLog]:
    """Parse, validate, and persist a log entry."""
    ingest = IngestPayload(data)

    if not ingest.is_valid:
        logger.warning("Invalid log payload", errors=ingest.errors)
        return None

    log_data = ingest.to_log()

    # Parse timestamps
    def parse_dt(val):
        if not val:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace("Z", "+00:00"))

    log = InferenceLog(
        id=uuid.uuid4(),
        conversation_id=log_data["conversation_id"],
        provider=log_data["provider"],
        model=log_data["model"],
        request_timestamp=parse_dt(log_data["request_timestamp"]) or datetime.now(timezone.utc),
        response_timestamp=parse_dt(log_data["response_timestamp"]),
        latency_ms=log_data["latency_ms"],
        time_to_first_token_ms=log_data["time_to_first_token_ms"],
        prompt_tokens=log_data["prompt_tokens"],
        completion_tokens=log_data["completion_tokens"],
        total_tokens=log_data["total_tokens"],
        status=RequestStatus(log_data["status"]) if log_data["status"] in RequestStatus._value2member_map_ else RequestStatus.success,
        error_message=log_data["error_message"],
        is_streaming=log_data["is_streaming"],
        input_preview=log_data["input_preview"],
        output_preview=log_data["output_preview"],
        extra_metadata=log_data["extra_metadata"],
    )

    db.add(log)
    await db.flush()
    logger.info("Log stored", log_id=str(log.id), provider=log.provider, model=log.model)
    return log
