# Technical Architecture

## High-Level Architecture

SewaStaff AI is a WhatsApp-native AI staff rental platform. Users interact with AI staff inside WhatsApp groups. The system routes each message through deterministic interceptors first, then through an LLM persona with RAG memory when needed.

```text
WhatsApp Group
   ↓
WAHA GoWS WebSocket
   ↓
waha_ws_listener.py (Worker)
   ↓
┌─────────────────────────────────────────────┐
│ Layer 1: Deterministic Interceptors          │
│ - Finance transaction                        │
│ - Finance query / balance                    │
│ - Reminder create/list/cancel                │
└─────────────────────────────────────────────┘
   ↓ if not handled
┌─────────────────────────────────────────────┐
│ Layer 2: Persona LLM + RAG                   │
│ - Role prompt                                │
│ - Identity memories                          │
│ - Semantic memories via pgvector             │
│ - Knowledge items                            │
│ - Recent chat history                        │
└─────────────────────────────────────────────┘
   ↓
OpenRouter LLM
   ↓
WAHA Send Message
   ↓
Memory Extraction + Embedding + pgvector save
```

## Runtime Services

| Service | Container | Purpose |
|---------|-----------|---------|
| FastAPI App | `sewastaff-ai-app-1` | REST API, admin backend |
| Worker | `sewastaff-ai-worker-1` | WAHA WebSocket listener and schedulers |
| Frontend | `sewastaff-ai-frontend-1` | SvelteKit admin dashboard |
| Postgres | `sewastaff-ai-postgres-1` | Main DB + pgvector |
| Redis | `sewastaff-ai-redis-1` | Cache/queue support |
| WAHA | `app-waha-1` | WhatsApp bridge (external/shared) |

## Message Processing Pipeline

### 1. Inbound Message

WAHA emits message events via WebSocket:

```text
ws://app-waha-1:3000/ws?session=default&events=message&x-api-key=***
```

The worker normalizes the payload into `NormalizedEvent`.

### 2. Group Binding Lookup

`group_bindings` maps WhatsApp group IDs to rented AI staff instances:

```text
group_id → rental_id → tenant_id + template_id
```

If no binding exists, the message is ignored or handled as unbound.

### 3. Layer 1: Deterministic Interceptors

Interceptors run before persona LLM. They prevent role persona from blocking universal utilities like finance and reminders.

#### Finance Transaction
Example input:

```text
Beli cilok 10rb
Jajan anak 35 rb dua kali
Transfer ortu 445 rb
```

Flow:

```text
Regex pre-filter
  → finance_extractor.py (LLM JSON extraction)
  → finance_service.py save transaction
  → hardcoded success response
```

Hardcoded response example:

```text
✅ Pengeluaran *Rp10.000* berhasil dicatat.
Kategori: Makanan
Keterangan: Beli cilok

⚠️ Peringatan: Saldo bulan ini minus! Pengeluaran melebihi pemasukan.
```

#### Finance Query
Example input:

```text
Sisa saldo
Pengeluaran bulan ini
Rekap keuangan
```

Flow:

```text
Regex query detection
  → finance_extractor.py query extraction
  → finance_service.py SQL aggregation
  → hardcoded summary response
```

#### Reminder
Example input:

```text
Ingatkan Satya 5 menit lagi sarapan
Ingatkan rapat besok jam 10 dengan PT Asia
Ingatkan shalat dan mengaji setiap hari jam 5 pagi
```

Flow:

```text
Reminder detection
  → reminder_extractor.py
  → reminders table
  → scheduler sends reminder later
```

Reminder is intentionally role-independent. HR, CS, Sales, Accounting, and PA must all accept reminders.

### 4. Layer 2: Persona LLM

If no interceptor handles the message, the worker builds a rich LLM context.

`context_builder.py` composes:

1. Base role prompt from `role_compiler.py`
2. Custom `base_prompt` from `staff_templates`
3. Identity memory from `staff_identity_memories`
4. Semantic memories from `staff_memories` using pgvector
5. Knowledge base items from `knowledge_items`
6. Recent chat history from `message_events`

Then the messages are sent to OpenRouter.

### 5. Memory Extraction

After AI replies, `memory_extractor.py` runs asynchronously/best-effort.

It asks a cheaper LLM to extract durable facts from the exchange:

```json
{
  "facts": [
    {
      "type": "preference",
      "content": "User wants reminder for shalat every morning",
      "category": "preference",
      "importance": 0.8,
      "is_identity": true,
      "key": "morning_prayer"
    }
  ]
}
```

Each fact is embedded via OpenRouter and stored in pgvector-backed columns.

## Key Code Files

| File | Responsibility |
|------|----------------|
| `backend/app/workers/waha_ws_listener.py` | Main WA worker, interceptors, routing |
| `backend/app/services/context_builder.py` | RAG context assembly |
| `backend/app/services/role_compiler.py` | System prompt compilation |
| `backend/app/services/memory_extractor.py` | Fact extraction and memory persistence |
| `backend/app/services/embedding_service.py` | OpenRouter embedding API |
| `backend/app/services/finance_extractor.py` | LLM finance extraction |
| `backend/app/services/finance_service.py` | Finance DB operations and summaries |
| `backend/app/services/reminder_extractor.py` | LLM reminder extraction |
| `backend/app/services/llm_client.py` | LLM routing via OpenRouter |

## Design Principles

### 1. Universal Utilities Must Bypass Persona

Finance and reminders are not role-specific. They are core tools every role should support.

Example failure avoided:

```text
User: Ingatkan Satya sarapan
HR Persona: I cannot set personal reminders because I am HR.
```

Solution: deterministic reminder handling + prompt override.

### 2. LLMs Extract, Database Decides

LLMs are used to interpret messy language, but final business logic is deterministic:

- Amount calculations happen in SQL
- Reminder schedules are stored in DB
- Balance warnings use DB totals
- Transaction status is explicit

### 3. RAG Memory, Not Raw Transcript Injection

The system does not blindly send all history to the LLM. It retrieves relevant memories through pgvector and adds recent short-term chat history.

### 4. Multi-Tenant First

Every important table is tied to `tenant_id`, `rental_id`, or `group_id`, allowing isolated staff rentals per customer/group.
