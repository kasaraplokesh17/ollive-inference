import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import structlog

from app.db.database import get_db
from app.models.conversation import Conversation, Message, ConversationStatus, MessageRole
from app.sdk.ollive_sdk import OlliveSDK, Provider
from app.services.pii_service import redact_pii
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])
logger = structlog.get_logger()

PROVIDER_MAP = {
    "openai": Provider.OPENAI,
    "anthropic": Provider.ANTHROPIC,
    "google": Provider.GOOGLE,
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "google": "gemini-1.5-flash",
}


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    provider: str = "anthropic"
    model: Optional[str] = None
    stream: bool = True


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    provider: str = "anthropic"


@router.post("/send")
async def send_message(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Validate provider
    if req.provider not in PROVIDER_MAP:
        raise HTTPException(400, f"Unknown provider: {req.provider}")

    # Check API key
    key_map = {
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "google": settings.GOOGLE_API_KEY,
    }
    if not key_map.get(req.provider):
        raise HTTPException(400, f"API key not configured for provider: {req.provider}")

    # Get or create conversation
    if req.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == uuid.UUID(req.conversation_id))
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if conv.status == ConversationStatus.cancelled:
            raise HTTPException(400, "Conversation is cancelled")
    else:
        conv = Conversation(
            id=uuid.uuid4(),
            title=req.message[:50] + ("..." if len(req.message) > 50 else ""),
            status=ConversationStatus.active,
        )
        db.add(conv)
        await db.flush()

    # Load conversation history
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    history = result.scalars().all()

    # Save user message
    user_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role=MessageRole.user,
        content=req.message,
        content_redacted=redact_pii(req.message) if settings.PII_REDACTION_ENABLED else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    await db.flush()

    # Build messages array for LLM
    llm_messages = [
        {"role": "system", "content": "You are a helpful assistant. Keep responses concise and clear."}
    ]
    for m in history[-20:]:  # last 20 messages for context
        llm_messages.append({"role": m.role.value, "content": m.content})
    llm_messages.append({"role": "user", "content": req.message})

    model = req.model or DEFAULT_MODELS[req.provider]
    sdk = OlliveSDK(
        provider=PROVIDER_MAP[req.provider],
        model=model,
        conversation_id=str(conv.id),
        pii_redact=settings.PII_REDACTION_ENABLED,
    )

    if req.stream:
        async def stream_response():
            full_response = ""
            try:
                gen = await sdk.chat(llm_messages, stream=True)
                async for token in gen:
                    full_response += token
                    yield f"data: {token}\n\n"
            except Exception as e:
                logger.error("Streaming error", error=str(e))
                yield f"data: [ERROR] {str(e)}\n\n"
                return
            finally:
                # Save assistant message
                if full_response:
                    async with db.begin_nested():
                        assistant_msg = Message(
                            id=uuid.uuid4(),
                            conversation_id=conv.id,
                            role=MessageRole.assistant,
                            content=full_response,
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(assistant_msg)
                    await db.commit()

                yield f"data: [DONE]\n\n"
                yield f"data: {{\"conversation_id\": \"{conv.id}\"}}\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "X-Conversation-ID": str(conv.id),
                "Cache-Control": "no-cache",
            }
        )
    else:
        content = await sdk.chat(llm_messages, stream=False)
        assistant_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role=MessageRole.assistant,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)
        await db.commit()
        return {
            "content": content,
            "conversation_id": str(conv.id),
        }
