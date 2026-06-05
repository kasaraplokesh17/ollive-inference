import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, Integer, JSON, Enum, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.db.database import Base


class RequestStatus(str, enum.Enum):
    success = "success"
    error = "error"
    cancelled = "cancelled"
    streaming = "streaming"


class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True, nullable=True
    )

    # Provider metadata
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(100), index=True)

    # Timing
    request_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    response_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True, index=True)
    time_to_first_token_ms: Mapped[float] = mapped_column(Float, nullable=True)

    # Token usage
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=True)

    # Request/Response
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.success, index=True
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    is_streaming: Mapped[bool] = mapped_column(Boolean, default=False)

    # Previews (truncated for storage)
    input_preview: Mapped[str] = mapped_column(Text, nullable=True)
    output_preview: Mapped[str] = mapped_column(Text, nullable=True)

    # Extra metadata
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    conversation: Mapped["Conversation"] = relationship(  # noqa: F821
        "Conversation", back_populates="inference_logs"
    )
