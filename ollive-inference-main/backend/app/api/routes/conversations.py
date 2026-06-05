import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
import structlog

from app.db.database import get_db
from app.models.conversation import Conversation, Message, ConversationStatus

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = structlog.get_logger()


def serialize_conv(c: Conversation, message_count: int = 0) -> dict:
    return {
        "id": str(c.id),
        "title": c.title,
        "status": c.status.value,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
        "message_count": message_count,
    }


def serialize_message(m: Message) -> dict:
    return {
        "id": str(m.id),
        "role": m.role.value,
        "content": m.content,
        "created_at": m.created_at.isoformat(),
    }


@router.get("/")
async def list_conversations(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(Conversation).order_by(Conversation.updated_at.desc())
    if status:
        q = q.where(Conversation.status == ConversationStatus(status))
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    convs = result.scalars().all()

    out = []
    for c in convs:
        count_result = await db.execute(
            select(func.count()).where(Message.conversation_id == c.id)
        )
        count = count_result.scalar() or 0
        out.append(serialize_conv(c, count))

    return {"conversations": out, "total": len(out)}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = messages_result.scalars().all()

    return {
        **serialize_conv(conv, len(messages)),
        "messages": [serialize_message(m) for m in messages],
    }


@router.post("/{conversation_id}/cancel")
async def cancel_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if conv.status == ConversationStatus.cancelled:
        raise HTTPException(400, "Already cancelled")

    conv.status = ConversationStatus.cancelled
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "cancelled", "id": conversation_id}


@router.post("/{conversation_id}/resume")
async def resume_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    conv.status = ConversationStatus.active
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "active", "id": conversation_id}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await db.delete(conv)
    await db.commit()
    return {"deleted": conversation_id}
