# Project Context: SewaStaff AI

## 1. Project Identity
- Project name: SewaStaff AI
- Repository: https://github.com/kuravista/sewastaff-ai (to be created)
- Workspace: `/openclaw/hermes/agents/sunday/projects/sewastaff-ai/`
- Main objective: Build a WhatsApp-native AI staff rental service for Indonesian SMBs.

## 2. Product Rules
- Non-negotiable business rules:
  - Reactive-only: AI responds only when messaged. Never initiates.
  - 1 role = 1 group = 1 memory container.
  - All responses must be safe: if unsure, ask the owner for clarification.
  - No broadcasting, no mass messaging, no unsolicited contact.
  - Every AI staff member must have a name, tone, and personality — never appear as a generic AI.
- Scope boundaries:
  - MVP roles: HR, PA, Sales Follow-up, Reminder, light Finance.
  - Channel: WhatsApp groups only (web trial for onboarding only).
  - Target: Tech-aware Indonesian business owners first.
  - Payment: Manual (bank transfer / QRIS) for MVP. No payment gateway.
- User expectations:
  - Onboarding under 5 minutes: search → select → get invite link → create group → active.
  - AI must feel human-paced (3–8 second response delay).
  - Owner sees everything in the group and can intervene naturally.

## 3. Technical Stack
- Frontend: SvelteKit (simple web UI for onboarding, trial chat, staff catalog).
- Backend: FastAPI (Python 3.11+), async throughout.
- Database: PostgreSQL (Server 2) — source of truth.
- Queue: Redis (Server 2) + ARQ worker — per-session pacing queue.
- Transport: WAHA GoWS (WhatsApp Web via Go engine, deployed on Server 2).
- LLM: OpenRouter API.
  - Primary: Gemini Flash (cheap, fast, vision-capable).
  - Fallback: OpenAI GPT-4o-mini.
- Infrastructure: Docker Compose on Server 2. Caddy reverse proxy on Server 2.
- Notifications: Telegram Bot API (for admin alerts: session down, billing, errors).

## 4. Architecture Conventions
- Module boundaries:
  - `api/` — HTTP endpoints (auth, staff, rentals, billing, webhooks).
  - `services/` — Business logic (waha_client, role_builder, llm_client, memory, billing).
  - `workers/` — ARQ background workers (per-session message queue consumer).
  - `models/` — SQLAlchemy models.
  - `schemas/` — Pydantic schemas for event normalization.
- Preferred patterns:
  - Event-driven: normalize WAHA webhook events into a strict internal schema before processing.
  - Adapter pattern: WAHA is a transport adapter. Business logic never touches WAHA directly.
  - Per-session queue: each `session_id` gets its own Redis queue with independent pacing.
  - Role compiler: roles are templates + user traits, never freeform prompts.
- Anti-patterns to avoid:
  - No global async queue (ban risk is per-number).
  - No Celery (overkill for IO-heavy async workloads).
  - No n8n in critical message path.
  - No Redis as source of truth.
  - No raw WAHA webhook events stored directly — always normalize first.
- Multi-tenant isolation:
  - Tenant = owner account.
  - Group = tenancy boundary for AI context.
  - Session = pacing boundary for anti-ban.

## 5. Code Conventions
- Naming style: snake_case for Python, kebab-case for files.
- File organization: one module per concern, grouped by domain.
- Error handling rules:
  - All external API calls wrapped in try/except with structured logging.
  - Failed LLM calls → fallback model → graceful error message to user.
  - Failed WAHA sends → retry queue (max 3) → admin Telegram alert.
- Logging rules:
  - Structured JSON logs.
  - `correlation_id` on every event (for tracing webhook → LLM → response).
  - No secrets in logs.
- Validation rules:
  - Pydantic v2 for all input/output schemas.
  - Webhook signature validation (if WAHA provides it).
  - Rate limiting on API endpoints.

## 6. Testing Expectations
- Minimum test types required: Unit tests for services, integration tests for webhook flow.
- What must always be covered: Event normalization, deduplication, role compiler, queue pacing logic.
- What can be manual for now: End-to-end WhatsApp flow (requires real WAHA session).

## 7. Safety / Ops Constraints
- Secret handling: `.env` file, never committed. `.env.example` for reference.
- Rate limits / quotas:
  - WAHA: 3–8 second delay between messages, max 5 identical messages/hour.
  - OpenRouter: token budget per session, fallback on quota hit.
  - API: rate limit onboarding endpoints.
- Destructive actions requiring caution:
  - Deleting a WAHA session (irreversible, loses session state).
  - Removing a group binding (loses AI memory context).
  - Resetting billing (manual admin action only).
- Backup / rollback expectations:
  - PostgreSQL daily backups on Server 2.
  - Docker images tagged with git SHA for rollback.
- WhatsApp anti-ban:
  - Number warmup: week 1 max 50–100 msgs/day, scale 20%/day.
  - 2–3 WAHA sessions for MVP. Rotate if one gets flagged.
  - Session watchdog: auto-detect session drop → notify admin via Telegram.
  - Queue per session: independent pacing, no cross-contamination.

## 8. AI Agent Rules
- Hermes should always: Lead architecture decisions, review all PRs, handle deployment.
- Pi may help with: Isolated module implementation, test writing, debugging.
- Pi should not decide: Product direction, pricing, scope, or role definitions.
- Required review before merge: Any change to event pipeline, queue logic, or LLM prompt templates.

## 9. Deployment
- Server 1 (openclaw): Source code repo, DNS/Cloudflare config.
- Server 2 (openclaw-support): Runtime target. Docker Compose.
  - FastAPI app
  - PostgreSQL
  - Redis
  - WAHA instances
  - Caddy reverse proxy
- Domain: `sewastaffai.wuz.web.id` → Cloudflare DNS → Server 2 Caddy.
- Docker Compose services:
  - `app` (FastAPI)
  - `worker` (ARQ)
  - `postgres`
  - `redis`
  - `waha` (1–3 instances)
  - `caddy` (reverse proxy + TLS)

## 10. Media Handling Policy
- Text: ✅ Core. Direct to LLM.
- Image: ✅ MVP. Gemini vision. Download → inject as image input.
- PDF/Document: ❌ Phase 2. Reply "share via link saja".
- Video: ❌ Out of scope.
- Audio/Voice note: ❌ Phase 2. Reply "ketik saja ya".
- Link: ⚠️ Treat as text. No auto-fetch.
- Sticker/GIF/Reaction: ❌ Ignore / no response.

## 11. Event Schema (Normalized)
```json
{
  "event_id": "uuid",
  "session_id": "string",
  "group_id": "string",
  "sender_id": "string",
  "message_type": "text|image|document|audio|video|sticker",
  "message_text": "string",
  "media_url": "string|null",
  "media_mime": "string|null",
  "timestamp": "ISO 8601",
  "is_from_me": false,
  "correlation_id": "uuid"
}
```
