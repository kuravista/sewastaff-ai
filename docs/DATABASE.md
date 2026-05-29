# Database Schema

## Connection

| Parameter | Value |
|-----------|-------|
| Host (Docker internal) | `sewastaff-ai-postgres-1` |
| Port | `5432` |
| Database | `sewastaff` |
| Username | `sewastaff` |
| Image | `pgvector/pgvector:pg16` |

## pgvector Extension

pgvector enables semantic search on AI embeddings. It is a PostgreSQL extension, not a table.

```sql
-- Verify extension is active
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
-- Result: vector | 0.7.x

-- Check which columns use vector type
SELECT table_name, column_name, udt_name
FROM information_schema.columns
WHERE udt_name = 'vector';
-- Results:
-- staff_memories.embedding    | vector
-- knowledge_items.embedding   | vector
-- staff_episodes.embedding    | vector
```

### Vector Dimensions

All embeddings use `vector(1536)` — matching OpenAI `text-embedding-3-small`.

### HNSW Indexes

```sql
-- staff_memories
CREATE INDEX idx_staff_memories_embedding
  ON staff_memories USING hnsw (embedding vector_cosine_ops);

-- staff_episodes
CREATE INDEX idx_episodes_embedding
  ON staff_episodes USING hnsw (embedding vector_cosine_ops);

-- knowledge_items
CREATE INDEX idx_knowledge_items_embedding
  ON knowledge_items USING hnsw (embedding vector_cosine_ops);
```

### Semantic Search Query

```sql
-- Find memories most similar to a query vector
SELECT id, content,
       1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
FROM staff_memories
WHERE rental_id = :rental_id AND embedding IS NOT NULL
ORDER BY embedding <=> CAST(:query_vec AS vector)
LIMIT 15;
```

Operator reference:
- `<=>` cosine distance (most common)
- `<->` L2 distance
- `<#>` inner product

## Tables

### staff_templates

AI staff role definitions. Seeded on first startup.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| slug | TEXT | Unique identifier: hr, pa, akuntansi, cs, sales |
| name | TEXT | Display name: Mbak Sera, Mas Dika, etc. |
| specialty | TEXT | Role specialty description |
| base_prompt | TEXT | Custom system prompt injected into LLM |
| avatar_emoji | TEXT | Emoji representation |
| price_monthly_idr | INT | Monthly rental price |
| is_active | BOOLEAN | Soft enable/disable |

### tenants

Multi-tenant business accounts.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | TEXT | Business name |
| created_at | TIMESTAMPTZ | Registration timestamp |

### rental_instances

Active staff rentals. One rental = one staff in one group.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK → tenants |
| template_id | UUID | FK → staff_templates |
| custom_traits | JSONB | Business info: name, description, products, FAQ, hours |
| status | TEXT | active, expired, cancelled |
| started_at | TIMESTAMPTZ | Rental start |
| expires_at | TIMESTAMPTZ | Rental end |

### group_bindings

Maps WhatsApp groups to rental instances.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| group_id | TEXT | WhatsApp group JID |
| rental_id | UUID | FK → rental_instances |

### message_events

Chat history for context and debugging.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| rental_id | UUID | FK → rental_instances |
| group_id | TEXT | WhatsApp group JID |
| sender_id | TEXT | WhatsApp sender JID |
| direction | TEXT | inbound or outbound |
| message_text | TEXT | Message content |
| timestamp | TIMESTAMPTZ | Message time |

### staff_memories

Extracted facts with semantic embeddings. Core long-term memory.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| rental_id | UUID | FK → rental_instances |
| type | TEXT | preference, fact, complaint |
| content | TEXT | Extracted fact (max 100 chars) |
| source | TEXT | chat_extraction, manual |
| confidence | FLOAT | Extraction confidence |
| embedding | vector(1536) | Semantic embedding |
| created_at | TIMESTAMPTZ | Extraction time |

### staff_identity_memories

Core identity/rules that are ALWAYS injected into context.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| rental_id | UUID | FK → rental_instances |
| category | TEXT | preference, fact, procedure |
| key | TEXT | Short key: tone, target_customer, jam_kerja |
| value | TEXT | The identity fact |
| importance | FLOAT | 0.0–1.0 |
| confirmed | BOOLEAN | User confirmed |
| updated_at | TIMESTAMPTZ | Last update |

### staff_episodes

Event-type memories with embeddings.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| rental_id | UUID | FK → rental_instances |
| group_id | TEXT | WhatsApp group |
| event_type | TEXT | customer_interaction, etc. |
| actor_id | TEXT | Who triggered |
| summary | TEXT | Event summary |
| importance | FLOAT | 0.0–1.0 |
| business_impact | FLOAT | Optional impact score |
| embedding | vector(1536) | Semantic embedding |
| source_event_id | TEXT | Reference to message_event |
| occurred_at | TIMESTAMPTZ | When it happened |

### financial_transactions

All recorded financial transactions.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| rental_id | UUID | FK → rental_instances |
| group_id | TEXT | WhatsApp group |
| sender_id | TEXT | Who reported |
| tx_type | TEXT | income, expense, transfer |
| amount_idr | INT | Amount in IDR |
| currency | TEXT | Default: IDR |
| category | TEXT | Makanan, Kendaraan, etc. |
| merchant | TEXT | Optional merchant name |
| description | TEXT | Human-readable description |
| transaction_date | TIMESTAMPTZ | When transaction occurred |
| source | TEXT | text or image |
| image_url | TEXT | Receipt image if from photo |
| ocr_text | TEXT | OCR result if from image |
| confidence | FLOAT | Extraction confidence |
| status | TEXT | confirmed, pending |

**Business rule:** `transfer` type is counted as **expense** in balance calculations (no multi-account system yet).

### reminders

Scheduled reminders with recurrence support.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| rental_id | UUID | FK → rental_instances |
| group_id | TEXT | WhatsApp group |
| title | TEXT | Reminder title |
| description | TEXT | Optional details |
| trigger_at | TIMESTAMPTZ | When to fire |
| recurrence | TEXT | daily, weekly, monthly, or NULL |
| status | TEXT | pending, sent, cancelled |

### knowledge_items

Uploaded knowledge base for staff.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| rental_id | UUID | FK → rental_instances |
| type | TEXT | faq, product, policy |
| source_url | TEXT | Optional source |
| content | TEXT | Raw knowledge content |
| summary | TEXT | AI-generated summary |
| embedding | vector(1536) | Semantic embedding |
| status | TEXT | active, pending |

## ORM vs Raw SQL

pgvector columns require explicit `CAST(:param AS vector)` in SQL. The SQLAlchemy ORM models declare embedding columns as `String`/`Text`, so vector writes must use raw SQL via `sqlalchemy.text()`:

```python
from sqlalchemy import text as sa_text

await db.execute(sa_text(
    "INSERT INTO staff_memories (id, rental_id, type, content, source, confidence, embedding) "
    "VALUES (gen_random_uuid(), :rid, :type, :content, :source, :conf, CAST(:emb AS vector))"
), {
    "rid": str(rental_id),
    "type": "preference",
    "content": "User prefers formal tone",
    "source": "chat_extraction",
    "conf": 0.9,
    "emb": str(embedding_vector),
})
```

**Never** pass embedding values through ORM model constructors — PostgreSQL will reject `character varying` for `vector` columns.
