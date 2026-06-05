"""
Async worker: drains Redis queue and processes logs.
Event-based architecture using Redis pub/sub + queue.
"""

import asyncio
import json
import signal
import structlog

from app.db.database import AsyncSessionLocal
from app.db.redis_client import init_redis, get_redis, close_redis
from app.services.ingestion import INGEST_QUEUE, process_log

logger = structlog.get_logger()
running = True


def handle_shutdown(sig, frame):
    global running
    logger.info("Shutdown signal received", signal=sig)
    running = False


async def worker_loop():
    await init_redis()
    redis = await get_redis()
    logger.info("Worker started, listening on queue", queue=INGEST_QUEUE)

    while running:
        try:
            # Block for up to 1s, then loop (allows checking `running`)
            item = await redis.brpop(INGEST_QUEUE, timeout=1)
            if not item:
                continue

            _, raw = item
            data = json.loads(raw)

            async with AsyncSessionLocal() as db:
                await process_log(data, db)
                await db.commit()

            logger.info("Worker processed log", provider=data.get("provider"))
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in queue", error=str(e))
        except Exception as e:
            logger.error("Worker error", error=str(e))
            await asyncio.sleep(1)

    await close_redis()
    logger.info("Worker stopped")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    asyncio.run(worker_loop())
