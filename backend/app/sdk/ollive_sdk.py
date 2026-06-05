"""
Ollive Inference SDK
Lightweight wrapper around LLM providers that captures inference metadata.
"""

import time
import uuid
import json
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, Any
from enum import Enum
import structlog
import httpx

logger = structlog.get_logger()


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class InferenceMetadata:
    def __init__(self):
        self.request_id = str(uuid.uuid4())
        self.provider: Optional[str] = None
        self.model: Optional[str] = None
        self.request_timestamp: Optional[datetime] = None
        self.response_timestamp: Optional[datetime] = None
        self.latency_ms: Optional[float] = None
        self.time_to_first_token_ms: Optional[float] = None
        self.prompt_tokens: Optional[int] = None
        self.completion_tokens: Optional[int] = None
        self.total_tokens: Optional[int] = None
        self.status: str = "success"
        self.error_message: Optional[str] = None
        self.is_streaming: bool = False
        self.input_preview: Optional[str] = None
        self.output_preview: Optional[str] = None
        self.extra: dict = {}

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "request_timestamp": self.request_timestamp.isoformat() if self.request_timestamp else None,
            "response_timestamp": self.response_timestamp.isoformat() if self.response_timestamp else None,
            "latency_ms": self.latency_ms,
            "time_to_first_token_ms": self.time_to_first_token_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "status": self.status,
            "error_message": self.error_message,
            "is_streaming": self.is_streaming,
            "input_preview": self.input_preview,
            "output_preview": self.output_preview,
            "extra": self.extra,
        }


class OlliveSDK:
    """
    Lightweight inference wrapper that logs all LLM calls.
    Supports OpenAI, Anthropic, and Google Gemini.
    """

    INGESTION_ENDPOINT = "http://backend:8000/api/v1/ingest/log"

    def __init__(
        self,
        provider: Provider,
        model: str,
        conversation_id: Optional[str] = None,
        ingestion_url: Optional[str] = None,
        pii_redact: bool = True,
    ):
        self.provider = provider
        self.model = model
        self.conversation_id = conversation_id
        self.ingestion_url = ingestion_url or self.INGESTION_ENDPOINT
        self.pii_redact = pii_redact
        self._client = httpx.AsyncClient(timeout=5.0)

    async def _send_log(self, metadata: InferenceMetadata):
        """Send log to ingestion pipeline asynchronously (fire-and-forget)."""
        try:
            payload = metadata.to_dict()
            if self.conversation_id:
                payload["conversation_id"] = self.conversation_id
            await self._client.post(self.ingestion_url, json=payload)
        except Exception as e:
            logger.warning("Failed to send inference log", error=str(e))

    def _preview(self, text: str, max_len: int = 200) -> str:
        if not text:
            return ""
        if self.pii_redact:
            from app.services.pii_service import redact_pii
            text = redact_pii(text) or text
        return text[:max_len] + ("..." if len(text) > max_len else "")

    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        **kwargs
    ) -> Any:
        meta = InferenceMetadata()
        meta.provider = self.provider
        meta.model = self.model
        meta.is_streaming = stream
        meta.request_timestamp = datetime.now(timezone.utc)
        meta.input_preview = self._preview(
            messages[-1].get("content", "") if messages else ""
        )

        start_time = time.perf_counter()

        try:
            if self.provider == Provider.OPENAI:
                return await self._openai_chat(messages, stream, meta, start_time, **kwargs)
            elif self.provider == Provider.ANTHROPIC:
                return await self._anthropic_chat(messages, stream, meta, start_time, **kwargs)
            elif self.provider == Provider.GOOGLE:
                return await self._google_chat(messages, stream, meta, start_time, **kwargs)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        except Exception as e:
            meta.status = "error"
            meta.error_message = str(e)
            meta.latency_ms = (time.perf_counter() - start_time) * 1000
            meta.response_timestamp = datetime.now(timezone.utc)
            await self._send_log(meta)
            raise

    async def _openai_chat(self, messages, stream, meta, start_time, **kwargs):
        from openai import AsyncOpenAI
        from app.core.config import settings
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        if stream:
            return self._openai_stream(client, messages, meta, start_time, **kwargs)
        else:
            response = await client.chat.completions.create(
                model=self.model, messages=messages, **kwargs
            )
            meta.latency_ms = (time.perf_counter() - start_time) * 1000
            meta.response_timestamp = datetime.now(timezone.utc)
            meta.prompt_tokens = response.usage.prompt_tokens if response.usage else None
            meta.completion_tokens = response.usage.completion_tokens if response.usage else None
            meta.total_tokens = response.usage.total_tokens if response.usage else None
            content = response.choices[0].message.content
            meta.output_preview = self._preview(content)
            await self._send_log(meta)
            return content

    async def _openai_stream(self, client, messages, meta, start_time, **kwargs) -> AsyncGenerator[str, None]:
        first_token = True
        full_text = ""
        async with client.chat.completions.stream(
            model=self.model, messages=messages, **kwargs
        ) as stream:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    if first_token:
                        meta.time_to_first_token_ms = (time.perf_counter() - start_time) * 1000
                        first_token = False
                    full_text += token
                    yield token

        meta.latency_ms = (time.perf_counter() - start_time) * 1000
        meta.response_timestamp = datetime.now(timezone.utc)
        meta.output_preview = self._preview(full_text)
        await self._send_log(meta)

    async def _anthropic_chat(self, messages, stream, meta, start_time, **kwargs):
        import anthropic as anthropic_sdk
        from app.core.config import settings
        client = anthropic_sdk.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Separate system from messages
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        chat_messages = [m for m in messages if m["role"] != "system"]

        params = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            "messages": chat_messages,
        }
        if system_msg:
            params["system"] = system_msg

        if stream:
            return self._anthropic_stream(client, params, meta, start_time)
        else:
            response = await client.messages.create(**params)
            meta.latency_ms = (time.perf_counter() - start_time) * 1000
            meta.response_timestamp = datetime.now(timezone.utc)
            meta.prompt_tokens = response.usage.input_tokens
            meta.completion_tokens = response.usage.output_tokens
            meta.total_tokens = response.usage.input_tokens + response.usage.output_tokens
            content = response.content[0].text
            meta.output_preview = self._preview(content)
            await self._send_log(meta)
            return content

    async def _anthropic_stream(self, client, params, meta, start_time) -> AsyncGenerator[str, None]:
        first_token = True
        full_text = ""
        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                if first_token:
                    meta.time_to_first_token_ms = (time.perf_counter() - start_time) * 1000
                    first_token = False
                full_text += text
                yield text
            final = await stream.get_final_message()
            meta.prompt_tokens = final.usage.input_tokens
            meta.completion_tokens = final.usage.output_tokens
            meta.total_tokens = final.usage.input_tokens + final.usage.output_tokens

        meta.latency_ms = (time.perf_counter() - start_time) * 1000
        meta.response_timestamp = datetime.now(timezone.utc)
        meta.output_preview = self._preview(full_text)
        await self._send_log(meta)

    async def _google_chat(self, messages, stream, meta, start_time, **kwargs):
        import google.generativeai as genai
        from app.core.config import settings
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(self.model)

        # Convert messages to Gemini format
        history = []
        last_msg = None
        for m in messages:
            if m["role"] == "system":
                continue
            elif m["role"] == "user":
                last_msg = m["content"]
                if len(messages) > 1:
                    history.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                history.append({"role": "model", "parts": [m["content"]]})

        chat = model.start_chat(history=history[:-1] if history else [])

        if stream:
            return self._google_stream(chat, last_msg, meta, start_time)
        else:
            response = await chat.send_message_async(last_msg)
            meta.latency_ms = (time.perf_counter() - start_time) * 1000
            meta.response_timestamp = datetime.now(timezone.utc)
            if hasattr(response, "usage_metadata"):
                meta.prompt_tokens = response.usage_metadata.prompt_token_count
                meta.completion_tokens = response.usage_metadata.candidates_token_count
                meta.total_tokens = response.usage_metadata.total_token_count
            content = response.text
            meta.output_preview = self._preview(content)
            await self._send_log(meta)
            return content

    async def _google_stream(self, chat, message, meta, start_time) -> AsyncGenerator[str, None]:
        first_token = True
        full_text = ""
        async for chunk in await chat.send_message_async(message, stream=True):
            if chunk.text:
                if first_token:
                    meta.time_to_first_token_ms = (time.perf_counter() - start_time) * 1000
                    first_token = False
                full_text += chunk.text
                yield chunk.text

        meta.latency_ms = (time.perf_counter() - start_time) * 1000
        meta.response_timestamp = datetime.now(timezone.utc)
        meta.output_preview = self._preview(full_text)
        await self._send_log(meta)
