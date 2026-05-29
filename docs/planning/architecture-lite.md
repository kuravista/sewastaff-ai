# Architecture-lite: SewaStaff AI

## 1. Architecture Summary
SewaStaff AI is a multi-tenant, event-driven virtual assistant platform operating over WhatsApp. The system normalizes raw WhatsApp Webhook events into an internal schema, routes them through a per-session Redis queue for strict anti-ban pacing, and relies on FastAPI workers to compile role contexts, call OpenRouter LLMs (Gemini Flash), and deliver replies back via the WAHA GoWS transport layer. All persistent state and billing data live in PostgreSQL.

## 2. Stack Decisions
- **Frontend:** SvelteKit (Trial UI, Onboarding Form, Staff Catalog)
- **Backend:** FastAPI (Python 3.11+, async)
- **Database:** PostgreSQL 16
- **Async / queue:** Redis + ARQ (Async Redis Queue)
- **Hosting / deployment:** Docker Compose on Server 2 (Oracle ARM)
- **AI / LLM components:** OpenRouter (Gemini Flash as primary, GPT-4o-mini as fallback)
- **Transport:** WAHA GoWS (WhatsApp Web client)

## 3. Main Components
- **Ingress API (FastAPI)**
  - Responsibility: Receive WAHA webhooks, validate signatures, normalize to standard `message_event` schema, deduplicate, and enqueue.
  - Inputs / outputs: Raw WAHA JSON → Redis Queue enqueue.
- **Worker (ARQ)**
  - Responsibility: Consume messages from per-session queues, enforce pacing jitter (3-8s), load group/tenant context, call LLM, and send reply.
  - Inputs / outputs: Redis task → LLM call → WAHA API send.
- **Context Builder (Service)**
  - Responsibility: Compile system prompt by combining the Staff Template (role, tone) with Tenant Traits (business name, FAQ) and short-term conversation history.
  - Inputs / outputs: Group ID + Message → LLM-ready message array.
- **WAHA Manager (Service)**
  - Responsibility: Monitor session health, fetch group metadata, and provide an abstraction over WAHA's REST API.
  - Inputs / outputs: Internal method calls → WAHA HTTP requests.
- **Web UI (SvelteKit)**
  - Responsibility: Staff catalog browsing, business form submission, trial chat interface.
  - Inputs / outputs: User interaction → FastAPI REST endpoints.

## 4. Data Model
- **Tenant (User):**
  - Purpose: Business owner account and billing identity.
  - Key fields: `id`, `telegram_id` (for alerts), `created_at`.
- **Staff Template (Role):**
  - Purpose: Base definition of an AI persona.
  - Key fields: `id`, `name` (e.g., "Mbak Sera"), `specialty` (e.g., "HR"), `base_prompt`, `avatar_url`.
- **Rental Instance:**
  - Purpose: The specific instance of a staff member rented by a tenant.
  - Key fields: `id`, `tenant_id`, `template_id`, `custom_traits` (JSON), `status`, `expires_at`.
- **WhatsApp Group Binding:**
  - Purpose: Maps a physical WhatsApp group to a Rental Instance (Memory container).
  - Key fields: `group_id` (WAHA ID), `rental_id`, `session_id` (which WAHA instance handles it).
- **Message Event (History):**
  - Purpose: Short-term memory and audit log.
  - Key fields: `event_id`, `group_id`, `sender_id`, `message_type`, `content` (text/media_url), `is_from_me`, `timestamp`.

## 5. Integrations
- **WAHA GoWS:**
  - Why needed: WhatsApp transport layer (receive/send messages, group management).
  - Main failure mode: Session drop, QR expiry, rate limit ban.
  - Fallback / mitigation: Watchdog alerts admin via Telegram; per-session pacing queue.
- **OpenRouter (Gemini Flash):**
  - Why needed: LLM inference and vision analysis.
  - Main failure mode: API timeout, quota hit, model outage.
  - Fallback / mitigation: Automatic fallback to OpenAI GPT-4o-mini; graceful degradation reply if all fail.
- **Telegram Bot API:**
  - Why needed: Admin alerts for session drops, errors, and billing events.
  - Main failure mode: API unreachable.
  - Fallback / mitigation: Log to error stream.

## 6. Auth / Access / Tenant Model
- **Authentication approach:** Web session JWT for onboarding/trial; API keys for internal service-to-service if separated.
- **Authorization approach:** Tenant ID isolation. A tenant can only manage their own rentals and groups.
- **Multi-tenant assumptions:** A single WAHA session (number) handles multiple groups across different tenants. The `group_id` is the strict boundary for context. Messages from Group A never bleed into Group B context, even on the same WAHA session.

## 7. Operational Concerns
- **Logging:** JSON structured logs with `correlation_id` passing from webhook ingress down to LLM output and WAHA send.
- **Monitoring:** Telegram alerts for session disconnects and unhandled worker exceptions.
- **Retry / idempotency:** Webhooks deduplicated via `event_id` in Redis. Failed LLM/WAHA calls retried up to 3 times in ARQ with exponential backoff.
- **Backup / recovery:** Daily PostgreSQL dumps on Server 2. Recreate WAHA sessions via QR scan if numbers are banned.

## 8. Key Risks / Tradeoffs
- **Risk 1:** WhatsApp banning the WAHA number due to multi-tenant usage patterns. Mitigation: Strict pacing, no broadcasting, grouping, multiple number pools.
- **Risk 2:** Race conditions from duplicate webhooks. Mitigation: Strict Redis deduplication lock at ingress.
- **Tradeoff 1:** Using polling/queueing introduces artificial delay. Chosen over real-time to mimic human typing and avoid anti-spam triggers.
- **Tradeoff 2:** No n8n means all workflow logic is in code. Faster execution and better testing, but requires code deployments for trivial logic changes.

## 9. Recommended Build Order
1. **Infrastructure & Dummy Ingress:** Deploy Postgres, Redis, and a dummy FastAPI webhook receiver to log raw WAHA events and understand the shape.
2. **Event Pipeline & Queue:** Build the event normalization schema, deduplication logic, and ARQ worker to echo messages back with a 5-second delay.
3. **Core Data Model & LLM Integration:** Implement Tenant, Rental, and Group tables. Connect the ARQ worker to OpenRouter (Gemini Flash) with a hardcoded Staff Template.
4. **Context Builder & Vision:** Add short-term memory retrieval and image parsing support to the context builder.
5. **Web Onboarding & Admin:** Build the SvelteKit trial/onboarding UI and the Telegram alert watchdog for session health.
