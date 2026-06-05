# Ollive Inference Logger

A production-grade LLM inference logging and observability system. Multi-provider chatbot with near-real-time inference metadata capture, event-based ingestion pipeline, and dashboards.

## Quick Start (One Command)

```bash
# 1. Clone and enter
git clone <repo> && cd ollive-inference

# 2. Add your API keys
cp .env.example .env
# Edit .env and add at least one provider key

# 3. Launch everything
docker compose up --build
```

| Service | URL |
|---|---|
| Chat UI | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## Architecture Overview

```
┌──────────────┐    SSE stream    ┌─────────────────────────────────────┐
│   React UI   │ ◄──────────────► │         FastAPI Backend              │
│              │                  │  ┌──────────┐  ┌───────────────────┐ │
│  - Chat      │                  │  │  /chat   │  │  /ingest/log      │ │
│  - Convs     │                  │  │  /convs  │  │  /metrics         │ │
│  - Dashboard │                  │  └──────────┘  └───────────────────┘ │
└──────────────┘                  └────────────────────┬────────────────┘
                                                       │
                         ┌─────────────────────────────┤
                         │                             │
                    ┌────▼───────┐          ┌──────────▼─────────┐
                    │ PostgreSQL │          │  Redis             │
                    │            │          │  - Ingest queue    │
                    │ - convs    │          │  - Pub/sub         │
                    │ - messages │          └──────────┬─────────┘
                    │ - inf_logs │                     │
                    └────────────┘          ┌──────────▼─────────┐
                                            │  Async Worker      │
                                            │  (queue drainer)   │
                                            └────────────────────┘
```

### Ingestion Flow

1. Chat request hits `/api/v1/chat/send`
2. `OlliveSDK` wraps the LLM call, records timing/tokens
3. After response, SDK posts to `/api/v1/ingest/log` (fire-and-forget)
4. Ingestion endpoint validates payload, writes to Postgres **and** pushes to Redis queue
5. Background worker drains queue for any additional async processing
6. Metrics endpoints query Postgres for dashboards

### SDK Design

The `OlliveSDK` is a thin wrapper:

```python
sdk = OlliveSDK(provider=Provider.ANTHROPIC, model="claude-3-5-haiku-20241022", conversation_id="...")
content = await sdk.chat(messages, stream=True)  # returns async generator
```

It captures: `request_timestamp`, `response_timestamp`, `latency_ms`, `time_to_first_token_ms`, `prompt_tokens`, `completion_tokens`, `status`, `input_preview`, `output_preview`, and ships them to the ingestion endpoint automatically.

---

## Schema Design

### `conversations`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| title | VARCHAR(255) | First 50 chars of first message |
| status | ENUM | active / cancelled / completed |
| created_at | TIMESTAMPTZ | Indexed |
| updated_at | TIMESTAMPTZ | Updated on each message |

### `messages`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation_id | UUID FK | Cascades on delete |
| role | ENUM | user / assistant / system |
| content | TEXT | Raw content |
| content_redacted | TEXT | PII-scrubbed version |
| token_count | INT | Nullable |
| created_at | TIMESTAMPTZ | |

### `inference_logs`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation_id | UUID FK | Nullable (supports standalone SDK use) |
| provider | VARCHAR(50) | Indexed |
| model | VARCHAR(100) | Indexed |
| request_timestamp | TIMESTAMPTZ | Indexed |
| latency_ms | FLOAT | Indexed |
| time_to_first_token_ms | FLOAT | Streaming TTFT |
| prompt_tokens | INT | |
| completion_tokens | INT | |
| total_tokens | INT | |
| status | ENUM | success / error / cancelled / streaming |
| is_streaming | BOOL | |
| input_preview | TEXT | First 200 chars, PII-redacted |
| output_preview | TEXT | First 200 chars |
| error_message | TEXT | Nullable |
| extra_metadata | JSONB | Flexible extension field |

**Tradeoffs:**
- Previews capped at 200 chars to avoid large row sizes; full content lives in `messages`
- JSONB `extra_metadata` for forward-compat without schema migrations
- Separate `inference_logs` from `messages` — logs are write-heavy telemetry, messages are read-heavy conversation data. Separating allows different retention policies.
- No foreign key enforcement on `conversation_id` in logs (nullable) so the SDK can be used standalone outside chat

---

## Multi-Provider Support

Supported out of the box:

| Provider | Models |
|---|---|
| Anthropic | claude-3-5-haiku, claude-3-5-sonnet, claude-opus-4-5 |
| OpenAI | gpt-4o-mini, gpt-4o, gpt-4-turbo |
| Google | gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash-exp |

Switch provider per-request from the UI dropdown.

---

## Features

- ✅ Multi-turn chat with context window (last 20 messages)
- ✅ Streaming responses (SSE)
- ✅ Multi-provider (Claude, OpenAI, Gemini)
- ✅ Lightweight SDK/wrapper with automatic logging
- ✅ Ingestion pipeline with Redis event queue
- ✅ PII redaction (Presidio + regex fallback)
- ✅ Conversation management: list, cancel, resume, delete
- ✅ Observability dashboard: latency, throughput, error rate, token usage
- ✅ Latency histogram + provider breakdown
- ✅ Prometheus metrics endpoint
- ✅ Grafana provisioned with Prometheus datasource
- ✅ Docker Compose one-command setup
- ✅ Async background worker (event-based)

---

## Scaling Considerations

- **Ingestion**: Fire-and-forget POST from SDK means chat latency is unaffected by logging. Redis queue decouples ingestion spikes from DB writes.
- **DB**: inference_logs is append-only — partition by `created_at` monthly at high volume. Add read replicas for metrics queries.
- **Workers**: Multiple worker replicas can drain the same Redis queue safely (each `BRPOP` is atomic).
- **Streaming**: SSE over HTTP. At scale, replace with WebSockets or a dedicated streaming proxy.
- **API**: Stateless FastAPI workers — scale horizontally behind a load balancer.

## Failure Handling Assumptions

- SDK log failures are **silent** — a failed ingest POST never breaks the chat response
- Redis unavailability degrades gracefully — logs still go to Postgres via the sync path
- DB write failures on messages are surfaced as 500 errors to the user
- Worker uses exponential-style sleep on errors to avoid hot loops

---

## What I'd Improve With More Time

1. **k8s manifests** — Helm chart with HPA on backend and worker deployments
2. **Rate limiting** — per-IP and per-conversation on the chat endpoint
3. **Full message search** — pgvector for semantic search over conversation history
4. **Cost tracking** — per-provider token pricing table → cost per request
5. **Trace IDs** — W3C trace context propagation for end-to-end request tracing
6. **Auth** — JWT-based user accounts, per-user conversation isolation
7. **Retention policy** — TTL-based archival of old inference_logs
8. **Test suite** — pytest with async fixtures and provider mocks

---

## Project Structure

```
ollive-inference/
├── backend/
│   ├── app/
│   │   ├── api/routes/     # chat, conversations, ingest, metrics
│   │   ├── core/           # config, settings
│   │   ├── db/             # database, redis client
│   │   ├── models/         # SQLAlchemy models
│   │   ├── sdk/            # OlliveSDK wrapper
│   │   ├── services/       # ingestion pipeline, PII
│   │   ├── main.py
│   │   └── worker.py       # Redis queue worker
│   ├── alembic/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/     # chat, conversations, dashboard
│       ├── lib/            # api client, streaming
│       └── store/          # zustand state
├── infra/
│   ├── grafana/
│   └── prometheus/
└── docker-compose.yml
```
