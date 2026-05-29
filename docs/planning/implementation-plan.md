# Implementation Plan: SewaStaff AI

> **For Hermes:** Execute epic by epic. Use `subagent-driven-development` for isolated tasks. Never skip a validation step.

**Goal:** Build and deploy SewaStaff AI MVP — WhatsApp-native AI staff rental — to `sewastaffai.wuz.web.id` on Server 2.

**Architecture Summary:** Event-driven multi-tenant platform. WAHA GoWS receives/sends WA messages → FastAPI normalizes + deduplicates → ARQ workers consume per-session Redis queues with anti-ban pacing → Gemini Flash (vision-capable) generates responses → reply via WAHA. SvelteKit handles web catalog + trial + onboarding. PostgreSQL is source of truth.

**Tech Stack:**
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, asyncpg, ARQ, HTTPX, redis-py 7
- Frontend: SvelteKit 2 + Svelte 5, Vite, TypeScript
- DB: PostgreSQL 16
- Queue: Redis 7-alpine
- Transport: WAHA GoWS (pinned tag)
- LLM: OpenRouter (Gemini Flash primary, GPT-4o-mini fallback)
- Infra: Docker Compose v2, Caddy 2.11, Server 2 ARM Oracle

---

## Epic 0 — Repo & Infra Skeleton
**Objective:** Working Docker Compose on Server 2. Domain pointing live. Logging infrastructure ready before first line of business logic.

### Task 0.1 — Repo Structure
- **Purpose:** Establish canonical file layout. All future tasks depend on this.
- **Files:**
  ```
  sewastaff-ai/
  ├── backend/
  │   ├── app/
  │   │   ├── api/
  │   │   │   ├── __init__.py
  │   │   │   ├── webhooks_waha.py
  │   │   │   ├── staff.py
  │   │   │   ├── rentals.py
  │   │   │   ├── onboarding.py
  │   │   │   └── trial.py
  │   │   ├── services/
  │   │   │   ├── waha_client.py
  │   │   │   ├── role_compiler.py
  │   │   │   ├── llm_client.py
  │   │   │   ├── context_builder.py
  │   │   │   ├── media_handler.py
  │   │   │   └── telegram_notifier.py
  │   │   ├── workers/
  │   │   │   ├── settings.py
  │   │   │   └── message_handler.py
  │   │   ├── models/
  │   │   │   ├── tenant.py
  │   │   │   ├── staff_template.py
  │   │   │   ├── rental_instance.py
  │   │   │   ├── group_binding.py
  │   │   │   └── message_event.py
  │   │   ├── schemas/
  │   │   │   ├── waha_event.py
  │   │   │   └── normalized_event.py
  │   │   ├── core/
  │   │   │   ├── config.py
  │   │   │   ├── database.py
  │   │   │   ├── redis.py
  │   │   │   └── logging.py
  │   │   └── main.py
  │   ├── alembic/
  │   ├── tests/
  │   ├── Dockerfile
  │   ├── requirements.txt
  │   └── .env.example
  ├── frontend/
  │   ├── src/
  │   │   ├── routes/
  │   │   │   ├── +page.svelte          # Landing + catalog
  │   │   │   ├── staff/[id]/+page.svelte
  │   │   │   ├── try/[id]/+page.svelte # Trial chat
  │   │   │   ├── onboarding/+page.svelte
  │   │   │   └── dashboard/+page.svelte
  │   │   └── lib/
  │   ├── Dockerfile
  │   └── .env.example
  ├── docker-compose.yml
  ├── docker-compose.prod.yml
  ├── Caddyfile
  └── README.md
  ```
- **Validation:** `git ls-files` shows structure. `docker compose config` parses without error.
- **Owner:** Hermes

---

### Task 0.2 — Logging Infrastructure
- **Purpose:** Logging must be ready BEFORE any event processing code. Every log entry must have enough context to trace a message from webhook entry to WA reply without reading code.
- **Files:** `backend/app/core/logging.py`
- **Implementation:**
  ```python
  # Structured JSON logging — always emit these fields:
  # - timestamp (ISO 8601)
  # - level
  # - service (app / worker)
  # - correlation_id  ← MUST exist end-to-end
  # - session_id
  # - group_id
  # - event_id
  # - message (human readable)
  # - error (if exception: class + message + truncated traceback)

  # Use: structlog with JSONRenderer
  # NOT print(), NOT logging.info() raw, NOT f-string
  
  # Log entry points (MANDATORY):
  # 1. Webhook received           → level=INFO,  event_id, session_id, group_id
  # 2. Dedup hit (duplicate)      → level=DEBUG, event_id "duplicate, skipped"
  # 3. Enqueue success            → level=INFO,  event_id, queue_name
  # 4. Worker dequeue             → level=INFO,  event_id, session_id, group_id
  # 5. Media download start/done  → level=INFO,  media_url, mime, bytes
  # 6. LLM call start             → level=INFO,  model, token_estimate
  # 7. LLM call success           → level=INFO,  model, latency_ms, tokens_used
  # 8. LLM call failure           → level=ERROR, model, error, fallback_triggered=true/false
  # 9. Pacing delay               → level=DEBUG, delay_ms, session_id
  # 10. WAHA send start           → level=INFO,  group_id, message_preview (first 50 chars)
  # 11. WAHA send success         → level=INFO,  latency_ms
  # 12. WAHA send failure         → level=ERROR, attempt, max_attempts, error
  # 13. Session watchdog alert    → level=ERROR, session_id, "session_disconnected"
  # 14. Retry queued              → level=WARN,  event_id, attempt_n
  # 15. Dead letter (max retry)   → level=ERROR, event_id, "max_retry_exceeded"
  ```
- **Deps:** `structlog==24.*`, `python-json-logger` as fallback
- **Validation:**
  - `docker compose logs app | python -m json.tool` parses every line without error.
  - Grep `correlation_id` across `app` + `worker` logs → same ID traces full lifecycle.
- **Owner:** Hermes

---

### Task 0.3 — Docker Compose + Caddy + Domain
- **Purpose:** Full stack up on Server 2. Domain live.
- **Files:** `docker-compose.yml`, `Caddyfile`
- **docker-compose.yml services:**
  ```yaml
  services:
    app:
      build: ./backend
      env_file: .env
      ports: ["8000:8000"]
      depends_on: [postgres, redis, waha]
      logging: &json-logging
        driver: json-file
        options:
          max-size: "50m"
          max-file: "5"

    worker:
      build: ./backend
      command: python -m arq app.workers.settings.WorkerSettings
      env_file: .env
      depends_on: [postgres, redis]
      logging: *json-logging

    frontend:
      build: ./frontend
      ports: ["3000:3000"]
      env_file: frontend/.env
      logging: *json-logging

    postgres:
      image: postgres:16-alpine
      volumes: ["pgdata:/var/lib/postgresql/data"]
      env_file: .env

    redis:
      image: redis:7-alpine
      volumes: ["redisdata:/data"]
      command: redis-server --save 60 1 --loglevel warning

    waha:
      image: devlikeapro/waha-plus:latest   # pin exact tag pre-deploy
      ports: ["3001:3000"]
      volumes: ["wahadata:/app/.waha/sessions"]
      environment:
        WHATSAPP_DEFAULT_ENGINE: GOWS
        WAHA_PRINT_QR: "false"

    caddy:
      image: caddy:2.11-alpine
      ports: ["80:80", "443:443"]
      volumes:
        - ./Caddyfile:/etc/caddy/Caddyfile
        - caddy_data:/data
        - caddy_config:/config
  ```
- **Caddyfile:**
  ```
  sewastaffai.wuz.web.id {
      handle /api/* {
          reverse_proxy app:8000
      }
      handle /webhooks/* {
          reverse_proxy app:8000
      }
      handle {
          reverse_proxy frontend:3000
      }
  }
  ```
- **Cloudflare:** DNS A record `sewastaffai.wuz.web.id` → Server 2 IP, DNS-only (grey cloud).
- **Validation:**
  - `curl https://sewastaffai.wuz.web.id/api/health` → `{"status":"ok","version":"0.1.0"}`
  - `docker compose ps` → all services healthy.
  - TLS cert auto-provisioned by Caddy.
- **Owner:** Hermes

---

## Epic 1 — Database & Core Models
**Objective:** All entities migrated, testable, seeded with 5 staff templates.

### Task 1.1 — DB Config + Alembic Init
- **Purpose:** SQLAlchemy async engine + Alembic migration baseline.
- **Files:** `core/database.py`, `alembic/env.py`, `alembic.ini`
- **Config:**
  ```python
  # core/database.py
  # - async engine via asyncpg
  # - SessionLocal factory (async)
  # - Base declarative model
  # - health_check() coroutine for /health endpoint
  ```
- **Validation:** `alembic upgrade head` applies cleanly. `alembic current` shows head.
- **Owner:** Hermes

---

### Task 1.2 — All SQLAlchemy Models
- **Purpose:** Persistent schema for all 5 entities.
- **Files:** `models/*.py`
- **Schema:**
  ```sql
  -- tenants
  id UUID PK
  email TEXT UNIQUE
  name TEXT
  telegram_chat_id BIGINT        -- for alerts/billing notifs
  created_at TIMESTAMPTZ DEFAULT now()
  
  -- staff_templates
  id UUID PK
  slug TEXT UNIQUE               -- "hr", "pa", "sales", "akuntansi", "cs"
  name TEXT                      -- "Mbak Sera"
  specialty TEXT                 -- "HR & Rekrutmen"
  base_prompt TEXT               -- locked system prompt base
  avatar_emoji TEXT              -- "👩‍💼"
  price_monthly_idr INT          -- 99000
  is_active BOOL DEFAULT true
  
  -- rental_instances
  id UUID PK
  tenant_id UUID FK
  template_id UUID FK
  custom_traits JSONB            -- {bisnis: "...", faq: [...], jam_ops: "..."}
  status TEXT                    -- "trial" | "active" | "expired" | "suspended"
  started_at TIMESTAMPTZ
  expires_at TIMESTAMPTZ
  
  -- group_bindings
  id UUID PK
  rental_id UUID FK UNIQUE
  group_id TEXT                  -- WAHA group JID e.g. "120363xxx@g.us"
  session_id TEXT                -- which WAHA session
  bound_at TIMESTAMPTZ
  
  -- message_events
  id UUID PK
  event_id TEXT UNIQUE           -- WAHA event ID (dedup key)
  group_id TEXT
  sender_id TEXT
  message_type TEXT
  content TEXT                   -- text or media_url
  is_from_me BOOL
  timestamp TIMESTAMPTZ
  correlation_id UUID
  ```
- **Validation:** `alembic revision --autogenerate` produces correct migration. All FK constraints valid.
- **Owner:** Hermes

---

### Task 1.3 — Seed Staff Templates
- **Purpose:** 5 base staff templates in DB. Referenced by onboarding and catalog.
- **Files:** `alembic/seed_staff_templates.py`
- **Data:**
  ```python
  TEMPLATES = [
    {
      "slug": "hr",
      "name": "Mbak Sera",
      "specialty": "HR & Rekrutmen",
      "avatar_emoji": "👩‍💼",
      "price_monthly_idr": 99000,
      "base_prompt": "Kamu adalah Mbak Sera, Staff HR profesional..."
    },
    {
      "slug": "pa",
      "name": "Mas Dika",
      "specialty": "Personal Assistant",
      "avatar_emoji": "🗂️",
      "price_monthly_idr": 79000,
    },
    {
      "slug": "akuntansi",
      "name": "Mbak Rini",
      "specialty": "Keuangan & Akuntansi",
      "avatar_emoji": "📊",
      "price_monthly_idr": 99000,
    },
    {
      "slug": "cs",
      "name": "Kak Aldi",
      "specialty": "Customer Service",
      "avatar_emoji": "💬",
      "price_monthly_idr": 79000,
    },
    {
      "slug": "sales",
      "name": "Mas Rio",
      "specialty": "Sales Follow-up",
      "avatar_emoji": "🎯",
      "price_monthly_idr": 99000,
    },
  ]
  ```
- **Validation:** `SELECT slug, name FROM staff_templates;` returns 5 rows.
- **Owner:** Hermes

---

## Epic 2 — WAHA Event Pipeline
**Objective:** Message masuk dari WA → normalized → queued → echoed back. Logging end-to-end sudah terbaca.

### Task 2.1 — Event Schema (Normalized)
- **Purpose:** Internal event schema. Semua business logic pakai ini, bukan raw WAHA payload.
- **Files:** `schemas/waha_event.py`, `schemas/normalized_event.py`
- **NormalizedEvent:**
  ```python
  class NormalizedEvent(BaseModel):
      event_id: str        # WAHA message ID
      correlation_id: UUID = Field(default_factory=uuid4)
      session_id: str
      group_id: str
      sender_id: str
      message_type: Literal["text","image","document","audio","video","sticker","unknown"]
      message_text: str | None
      media_url: str | None
      media_mime: str | None
      timestamp: datetime
      is_from_me: bool
  ```
- **Validation:** Unit test: 5 raw WAHA payloads → normalized correctly. Unknown types → `message_type="unknown"`.
- **Owner:** Hermes

---

### Task 2.2 — Webhook Ingress + Deduplication
- **Purpose:** Receive WAHA webhook, normalize, dedup via Redis, enqueue.
- **Files:** `api/webhooks_waha.py`
- **Logic:**
  ```python
  @router.post("/webhooks/waha")
  async def receive_waha_event(payload: dict, ...):
      # 1. Parse raw payload → NormalizedEvent
      # 2. Log: webhook_received (event_id, session_id, group_id)
      # 3. Skip if is_from_me=True
      # 4. Skip if message_type not in ["text", "image"]  ← media filter
      # 5. Dedup: Redis SET NX "dedup:{event_id}" EX 3600
      #    → if already set: log duplicate_skipped, return 200
      # 6. Resolve group_id → group_binding → rental_instance
      #    → if no binding: log "no_binding_for_group", return 200
      # 7. Check rental status = "active"
      #    → if not: log "rental_inactive", return 200
      # 8. Enqueue to ARQ queue keyed by session_id
      # 9. Log: enqueue_success (event_id, queue=session_id)
      return {"status": "queued"}
  ```
- **Key rule:** Webhook ALWAYS returns 200. Never fail a webhook. Log errors internally.
- **Validation:**
  - POST duplicate event twice → second returns 200, log shows "duplicate_skipped".
  - POST event for unbound group → log shows "no_binding_for_group".
  - POST valid event → appears in ARQ queue.
- **Owner:** Hermes

---

### Task 2.3 — ARQ Worker + Per-Session Queue
- **Purpose:** Consume per-session queue. Apply pacing. Echo message back (no LLM yet).
- **Files:** `workers/settings.py`, `workers/message_handler.py`
- **Worker settings:**
  ```python
  class WorkerSettings:
      functions = [handle_message]
      queue_name = "default"       # ARQ default; session routing via job kwargs
      max_jobs = 10
      job_timeout = 30
      retry_jobs = True
      max_tries = 3
  ```
- **Per-session pacing:**
  ```python
  async def handle_message(ctx, event: dict):
      evt = NormalizedEvent(**event)
      log.info("worker_dequeue", event_id=evt.event_id, session_id=evt.session_id)

      # Acquire per-session lock (Redis SETNX TTL=30s)
      # If locked: re-queue with 5s delay, log "session_busy"
      
      # Pacing delay: random.uniform(3, 8) seconds
      delay = random.uniform(3000, 8000) / 1000
      log.debug("pacing_delay", delay_ms=int(delay*1000), session_id=evt.session_id)
      await asyncio.sleep(delay)
      
      # PHASE 1: Echo back (no LLM)
      reply = f"[ECHO] {evt.message_text}"
      await waha_client.send_text(evt.session_id, evt.group_id, reply)
      log.info("waha_send_success", group_id=evt.group_id)
  ```
- **Validation:**
  - Send a message to WA group → group receives echo reply after 3–8 second delay.
  - Send 3 messages rapidly → replies arrive spaced, not bursting.
  - Worker logs show full lifecycle per message.
- **Owner:** Hermes

---

### Task 2.4 — WAHA Client Abstraction
- **Purpose:** All WAHA REST calls in one place. Business logic never calls WAHA directly.
- **Files:** `services/waha_client.py`
- **Methods:**
  ```python
  class WAHAClient:
      async def send_text(session_id, group_id, text) -> None
      async def send_image(session_id, group_id, image_url, caption) -> None
      async def get_session_status(session_id) -> dict
      async def list_groups(session_id) -> list
      async def create_group(session_id, name, participants) -> dict
      async def get_group_invite_code(session_id, group_id) -> str
      async def download_media(media_url) -> bytes
  ```
- **Error handling:**
  ```python
  # All methods: try/except → log waha_call_error (method, status_code, error)
  # send_text/send_image: retry up to 3x with exponential backoff
  # After 3 failures: log "waha_send_dead_letter", notify admin via Telegram
  ```
- **Validation:** Unit test with HTTPX MockTransport. Test retry logic. Test dead letter trigger.
- **Owner:** Hermes

---

## Epic 3 — LLM Integration
**Objective:** Worker calls real LLM. Context-aware. Vision-capable. Fallback model works.

### Task 3.1 — LLM Client
- **Purpose:** OpenRouter abstraction with fallback and token logging.
- **Files:** `services/llm_client.py`
- **Logic:**
  ```python
  MODELS = {
      "primary": "google/gemini-flash-2.5",
      "fallback": "openai/gpt-4o-mini",
  }

  async def call_llm(messages: list, model="primary", has_image=False) -> str:
      model_id = MODELS[model]
      log.info("llm_call_start", model=model_id, message_count=len(messages))
      t0 = time.monotonic()
      try:
          response = await httpx_client.post(
              "https://openrouter.ai/api/v1/chat/completions",
              json={"model": model_id, "messages": messages},
              headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
              timeout=15.0
          )
          response.raise_for_status()
          latency_ms = int((time.monotonic() - t0) * 1000)
          result = response.json()
          tokens = result["usage"]["total_tokens"]
          log.info("llm_call_success", model=model_id, latency_ms=latency_ms, tokens=tokens)
          return result["choices"][0]["message"]["content"]
      except Exception as e:
          log.error("llm_call_failure", model=model_id, error=str(e), fallback_triggered=(model=="primary"))
          if model == "primary":
              return await call_llm(messages, model="fallback", has_image=has_image)
          raise
  ```
- **Validation:** Mock OpenRouter → test primary success. Test primary fail → fallback triggers. Logs show latency + tokens on every call.
- **Owner:** Hermes

---

### Task 3.2 — Context Builder
- **Purpose:** Build LLM message array from: system prompt (role + tenant traits) + conversation history.
- **Files:** `services/context_builder.py`
- **Logic:**
  ```python
  async def build_context(rental: RentalInstance, event: NormalizedEvent) -> list[dict]:
      # 1. Load staff template base_prompt
      # 2. Merge tenant custom_traits into prompt
      #    - {bisnis_name}, {bisnis_desc}, {faq}, {jam_operasional}
      # 3. Load last 20 messages from message_events for this group_id (ordered by timestamp)
      # 4. Build messages array:
      #    [
      #      {"role": "system", "content": compiled_system_prompt},
      #      {"role": "user",   "content": "..."},   # history
      #      {"role": "assistant", "content": "..."},
      #      ...
      #      {"role": "user", "content": current_message}  # or image content block
      #    ]
      # 5. If event.message_type == "image": replace last user content with vision block
  ```
- **Vision block:**
  ```python
  # For image type:
  {"role": "user", "content": [
      {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_data}"}},
      {"type": "text", "text": event.message_text or "Tolong analisis gambar ini."}
  ]}
  ```
- **Validation:** Unit test: text event → correct messages array. Image event → vision block present.
- **Owner:** Hermes

---

### Task 3.3 — Role Compiler
- **Purpose:** Compile final system prompt from template + tenant form input.
- **Files:** `services/role_compiler.py`
- **Template system:**
  ```python
  BASE_PROMPT_TEMPLATE = """
  Kamu adalah {staff_name}, {specialty} virtual untuk bisnis {bisnis_name}.

  Tentang bisnis ini:
  {bisnis_desc}

  Produk/jasa yang ditawarkan:
  {produk_jasa}

  Jam operasional:
  {jam_operasional}

  FAQ yang harus kamu hafal:
  {faq_block}

  Aturan mutlak:
  - Jawab hanya pertanyaan yang relevan dengan peranmu sebagai {specialty}.
  - Jika tidak tahu, katakan: "Nanti saya tanyakan ke tim dulu ya."
  - Jangan pernah berbohong tentang produk atau harga.
  - Jangan kirim pesan ke siapa pun tanpa diminta.
  - Selalu sopan, singkat, dan bantu selesaikan masalah.
  - Jika ada gambar: analisis dan berikan jawaban berdasarkan isinya.
  """
  
  def compile_prompt(template: StaffTemplate, traits: dict) -> str:
      faq_block = "\n".join([f"Q: {q}\nA: {a}" for q, a in traits.get("faq", {}).items()])
      return BASE_PROMPT_TEMPLATE.format(
          staff_name=template.name,
          specialty=template.specialty,
          bisnis_name=traits["bisnis_name"],
          bisnis_desc=traits["bisnis_desc"],
          produk_jasa=traits.get("produk_jasa", "-"),
          jam_operasional=traits.get("jam_operasional", "Senin–Jumat 09:00–17:00"),
          faq_block=faq_block or "-",
      )
  ```
- **Validation:** Unit test: given template + traits → output contains all fields. No template variable left as `{unfilled}`.
- **Owner:** Hermes

---

### Task 3.4 — Media Handler (Image)
- **Purpose:** Download image from WAHA media URL → base64 encode → return for vision.
- **Files:** `services/media_handler.py`
- **Logic:**
  ```python
  async def handle_image(media_url: str, mime: str) -> str:
      log.info("media_download_start", url=media_url, mime=mime)
      async with httpx.AsyncClient() as client:
          resp = await client.get(media_url, timeout=10.0)
          resp.raise_for_status()
          data = resp.content
          log.info("media_download_done", bytes=len(data), mime=mime)
          return base64.b64encode(data).decode()

  # Non-image types → return canned response text:
  UNSUPPORTED_REPLIES = {
      "document": "Maaf, saya belum bisa baca file. Kirim via link Google Drive ya 🙏",
      "audio":    "Maaf, saya belum bisa dengar voice note. Ketik saja ya 🙏",
      "video":    "Maaf, video belum didukung. Ketik atau kirim gambar saja 🙏",
      "sticker":  None,   # Ignore — no reply
      "unknown":  None,
  }
  ```
- **Validation:** Test with real image URL → base64 string valid. Test document type → returns correct canned string.
- **Owner:** Hermes

---

### Task 3.5 — Wire Worker → Full LLM Pipeline
- **Purpose:** Replace echo worker with real LLM pipeline.
- **Files:** `workers/message_handler.py` (full update)
- **Full pipeline:**
  ```python
  async def handle_message(ctx, event: dict):
      evt = NormalizedEvent(**event)
      log.info("worker_dequeue", **evt.log_fields())

      # 1. Pacing delay
      # 2. Load group_binding → rental_instance → staff_template
      # 3. Media filter (non-text/image → canned reply → done)
      # 4. Handle image: download → base64
      # 5. Context builder → messages array
      # 6. LLM call (with fallback)
      # 7. Pacing (typing delay)
      # 8. WAHA send reply
      # 9. Persist message_event to DB (both inbound + outbound)
  ```
- **Validation:** End-to-end: send real WA message → group receives contextual AI reply after 3–8s. Logs show 9 checkpoints.
- **Owner:** Hermes

---

## Epic 4 — Session Watchdog + Admin Alerts
**Objective:** Auto-detect session drops. Notify admin instantly via Telegram. Never silent failures.

### Task 4.1 — Telegram Notifier Service
- **Purpose:** Centralized admin notification. One import, one call.
- **Files:** `services/telegram_notifier.py`
- **Methods:**
  ```python
  async def alert_session_down(session_id: str) -> None
  async def alert_llm_dead_letter(event_id: str, group_id: str) -> None
  async def alert_send_dead_letter(event_id: str, group_id: str) -> None
  async def notify_rental_expiring(tenant: Tenant, rental: RentalInstance, days_left: int) -> None
  ```
- **Message format:**
  ```
  🔴 [SewaStaff AI] Session DOWN
  Session: wa-session-1
  Time: 2025-01-01 10:00 WIB
  Action: Login ke /waha/sessions dan scan ulang QR
  ```
- **Validation:** Call each method → message arrives in admin Telegram chat.
- **Owner:** Hermes

---

### Task 4.2 — Session Watchdog (ARQ Periodic)
- **Purpose:** Poll WAHA session status every 2 minutes. Alert if disconnected.
- **Files:** `workers/settings.py` (cron_jobs), `workers/session_watchdog.py`
- **Logic:**
  ```python
  async def check_sessions(ctx):
      sessions = settings.WAHA_SESSION_IDS  # ["wa-session-1", "wa-session-2"]
      for session_id in sessions:
          status = await waha_client.get_session_status(session_id)
          log.info("watchdog_check", session_id=session_id, status=status["engine_state"])
          if status["engine_state"] != "WORKING":
              log.error("session_disconnected", session_id=session_id, state=status["engine_state"])
              await telegram_notifier.alert_session_down(session_id)
  
  # ARQ cron:
  cron(check_sessions, minute={0, 2, 4, 6, 8, ...})  # every 2 minutes
  ```
- **Validation:** Stop WAHA container → within 2 minutes, Telegram receives alert with session ID.
- **Owner:** Hermes

---

## Epic 5 — Group Binding & Onboarding API
**Objective:** Webhook auto-detects new group join. Onboarding form registers rental. Group binds.

### Task 5.1 — Auto Group Binding via Webhook
- **Purpose:** When WAHA joins a group → auto-detect → match to pending rental → bind.
- **Files:** `api/webhooks_waha.py` (extend), `services/binding_service.py`
- **Logic:**
  ```python
  # WAHA emits group participant events
  # When event type = "group.join" and is_from_me=True:
  #   - group_id extracted
  #   - Find rental for tenant with status="trial" and no binding yet
  #   - Create group_binding record
  #   - Update rental status to "active"
  #   - Send welcome message to group
  #   - Log: "group_binding_created"
  ```
- **Welcome message (per template):**
  ```
  Halo! Saya {staff_name} 👋
  Saya siap bantu {specialty} untuk {bisnis_name}.
  Ketik pesan Anda dan saya akan balas secepatnya.
  ```
- **Validation:** Add WAHA number to a test group → welcome message appears → binding record in DB.
- **Owner:** Hermes

---

### Task 5.2 — Onboarding REST API
- **Purpose:** Frontend calls these to create tenant, rental, and get invite instructions.
- **Files:** `api/onboarding.py`
- **Endpoints:**
  ```
  POST /api/onboarding/start
  Body: {email, bisnis_name, bisnis_desc, produk_jasa, jam_operasional, faq: [{q,a}], template_slug}
  Response: {rental_id, invite_instructions: "Buat grup WA → invite nomor: +62xxx"}

  GET  /api/onboarding/status/{rental_id}
  Response: {status: "pending_bind" | "active", group_id?, bound_at?}

  GET  /api/staff
  Response: [{slug, name, specialty, avatar_emoji, price_monthly_idr, features: [...]}]

  GET  /api/staff/{slug}
  Response: full template detail
  ```
- **Validation:** POST onboarding → rental created in DB, status=trial. GET staff → 5 templates returned.
- **Owner:** Hermes

---

### Task 5.3 — Trial Chat API
- **Purpose:** Web trial: 10 messages, no WA. Uses same LLM pipeline but via HTTP.
- **Files:** `api/trial.py`
- **Endpoints:**
  ```
  POST /api/trial/start
  Body: {template_slug}
  Response: {trial_id, messages_remaining: 10}

  POST /api/trial/message
  Body: {trial_id, message: str}
  Response: {reply: str, messages_remaining: int}
  ```
- **Logic:**
  - Trial session stored in Redis (TTL 1 hour)
  - Max 10 messages enforced server-side
  - Uses role compiler with generic traits (no tenant form needed)
  - After limit: `{"reply": null, "messages_remaining": 0, "cta": "Aktifkan via WhatsApp Rp99k/bulan"}`
- **Validation:** POST 11 messages → 11th returns CTA. Session expires after 1 hour.
- **Owner:** Hermes

---

## Epic 6 — SvelteKit Frontend
**Objective:** Working web UI matching mockup. Connected to backend API.

### Task 6.1 — SvelteKit Project Init + Design System
- **Purpose:** Project init, Inter font, purple design tokens, reusable components.
- **Files:** `frontend/src/app.css`, `frontend/src/lib/components/`
- **Components:**
  ```
  StaffCard.svelte     # avatar, name, specialty, features, price, CTA buttons
  SearchBar.svelte     # rounded, placeholder, Cari button
  ChatBubble.svelte    # for trial chat + hero mock WA
  BottomNav.svelte     # sticky 5-tab mobile nav
  TrustItem.svelte     # icon + title + desc
  ```
- **Design tokens:**
  ```css
  --color-primary: #7C3AED;
  --color-primary-light: #EDE9FE;
  --color-bg: #FFFFFF;
  --color-text: #1F2937;
  --color-muted: #6B7280;
  --radius-card: 16px;
  --shadow-card: 0 2px 12px rgba(0,0,0,0.06);
  ```
- **Validation:** Dev server starts. Components render without errors.
- **Owner:** Hermes / Pi

---

### Task 6.2 — Landing Page + Catalog (`/`)
- **Purpose:** Homepage with hero, search, staff cards grid, trust section, CTA.
- **Files:** `frontend/src/routes/+page.svelte`
- **Fetches:** `GET /api/staff` on load.
- **Features:**
  - Search filters cards client-side by specialty/name.
  - Each card has [Coba] and [Sewa] CTAs.
  - Mock WA chat in hero (static HTML/CSS).
  - Trust strip horizontally scrollable.
- **Validation:** All 5 staff cards visible. Search "HR" → only HR card shown. [Coba] → navigates to `/try/hr`.
- **Owner:** Pi (implement) / Hermes (review)

---

### Task 6.3 — Trial Chat Page (`/try/[id]`)
- **Purpose:** 10-message free trial chat in web.
- **Files:** `frontend/src/routes/try/[id]/+page.svelte`
- **UI:**
  - Chat bubble list (user right, AI left with avatar).
  - Input bar + send button.
  - Message counter "8 pesan tersisa".
  - After limit: CTA card overlay.
- **Calls:** `POST /api/trial/start`, `POST /api/trial/message`.
- **Validation:** 10 messages cycle. 11th → CTA visible. AI replies render with avatar.
- **Owner:** Pi / Hermes

---

### Task 6.4 — Onboarding Page (`/onboarding`)
- **Purpose:** Business form → submit → show invite instructions.
- **Files:** `frontend/src/routes/onboarding/+page.svelte`
- **Steps:**
  1. Select role (from catalog).
  2. Fill form (bisnis name, desc, produk, jam ops, FAQ Q&A pairs).
  3. Submit → show: "Buat grup WA → invite nomor: `+62xxx`".
  4. Poll `/api/onboarding/status/{rental_id}` every 5s.
  5. When status=active → show: "✅ Staff AI Anda sudah aktif di grup!"
- **Validation:** Full form submit → rental in DB. Poll detects binding. Success state shows.
- **Owner:** Pi / Hermes

---

### Task 6.5 — Dashboard Page (`/dashboard`)
- **Purpose:** Minimal: list active rentals, status, expiry, total bill.
- **Files:** `frontend/src/routes/dashboard/+page.svelte`
- **Data shown per rental:**
  - Staff name + specialty + avatar
  - Status badge (aktif / trial / expired)
  - Group WA (masked: `Tim Marketing`)
  - Expires: `31 Jan 2026`
  - Price: `Rp99.000/bulan`
- **No analytics, no charts. Text only.**
- **Validation:** Rental from DB appears. Status badge correct color.
- **Owner:** Pi / Hermes

---

## Epic 7 — Hardening & Pre-Deploy
**Objective:** Safe to go live on `sewastaffai.wuz.web.id`.

### Task 7.1 — Secrets & Environment
- **Purpose:** All secrets in `.env`. `.env.example` committed. Zero secrets in code.
- **Files:** `.env`, `.env.example`
- **Required vars:**
  ```env
  # Postgres
  POSTGRES_USER=
  POSTGRES_PASSWORD=
  POSTGRES_DB=sewastaff
  DATABASE_URL=postgresql+asyncpg://...

  # Redis
  REDIS_URL=redis://redis:6379/0

  # WAHA
  WAHA_BASE_URL=http://waha:3000
  WAHA_API_KEY=
  WAHA_SESSION_IDS=wa-session-1,wa-session-2

  # OpenRouter
  OPENROUTER_API_KEY=

  # Telegram (admin alerts)
  TELEGRAM_BOT_TOKEN=
  TELEGRAM_ADMIN_CHAT_ID=

  # App
  APP_SECRET_KEY=
  APP_ENV=production
  ```
- **Validation:** `grep -r "sk-\|Bearer\|password" app/` → zero hits.
- **Owner:** Hermes

---

### Task 7.2 — Rate Limiting + Input Validation
- **Purpose:** Protect webhook + trial + onboarding endpoints.
- **Files:** `core/middleware.py`
- **Rules:**
  - `/webhooks/waha` → no rate limit (WAHA is trusted internal), but validate `X-WAHA-Signature` if configured.
  - `/api/trial/*` → 20 req/min per IP.
  - `/api/onboarding/*` → 5 req/min per IP.
  - All inputs: Pydantic v2 strict validation. Max text length 4000 chars.
- **Validation:** Hammer trial endpoint > 20 req/min → 429. Long input > 4000 chars → 422.
- **Owner:** Hermes

---

### Task 7.3 — Health & Readiness Endpoints
- **Purpose:** Docker + Caddy + monitoring need these.
- **Files:** `api/__init__.py` or `main.py`
- **Endpoints:**
  ```
  GET /api/health
  → {"status": "ok", "version": "0.1.0", "db": "ok", "redis": "ok", "timestamp": "..."}

  GET /api/ready
  → 200 if DB + Redis connected, 503 if not
  ```
- **Validation:** Kill postgres → `/api/ready` returns 503. Restore → 200.
- **Owner:** Hermes

---

### Task 7.4 — Full Integration Test Pass
- **Purpose:** Manual end-to-end smoke test on staging before declaring done.
- **Checklist:**
  ```
  □ POST /api/onboarding/start → rental created
  □ Add WAHA to WA group → welcome message sent
  □ Send text to group → AI replies with correct role context
  □ Send image to group → AI describes image
  □ Send voice note → AI says "ketik saja ya"
  □ Send sticker → no reply (ignore)
  □ Send 2 messages rapidly → replies spaced >3s
  □ POST /api/trial/message × 11 → CTA on 11th
  □ Stop WAHA container → Telegram alert within 2min
  □ docker compose logs app | python -m json.tool → all lines parse
  □ curl https://sewastaffai.wuz.web.id/api/health → {"status": "ok"}
  □ Frontend catalog → 5 cards visible
  □ Search "pa" → only PA card shown
  □ [Coba] button → trial chat works
  □ [Sewa] button → onboarding form opens
  □ Onboarding form submit → shows invite instructions
  □ Dashboard → rental status correct
  ```
- **Owner:** Hermes (all) + manual testing by user (WA group flow)

---

## Review Gates

- **Gate 0:** Docker Compose up + `/api/health` OK + domain live.
- **Gate 1:** WAHA echo pipeline e2e working. Logs parseable.
- **Gate 2:** LLM pipeline e2e. Context correct. Image processed. Fallback works.
- **Gate 3:** Watchdog alerts working. Retry/dead-letter working.
- **Gate 4:** Full integration test checklist 100%.

---

## Logging Cheatsheet (Quick Reference)

| Log Entry | Level | Required Fields |
|---|---|---|
| `webhook_received` | INFO | event_id, session_id, group_id |
| `duplicate_skipped` | DEBUG | event_id |
| `no_binding_for_group` | INFO | group_id |
| `rental_inactive` | INFO | rental_id, status |
| `enqueue_success` | INFO | event_id, queue |
| `worker_dequeue` | INFO | event_id, session_id, group_id |
| `pacing_delay` | DEBUG | delay_ms, session_id |
| `media_download_start` | INFO | url, mime |
| `media_download_done` | INFO | bytes, mime |
| `llm_call_start` | INFO | model, message_count |
| `llm_call_success` | INFO | model, latency_ms, tokens |
| `llm_call_failure` | ERROR | model, error, fallback_triggered |
| `waha_send_start` | INFO | group_id, preview |
| `waha_send_success` | INFO | group_id, latency_ms |
| `waha_send_failure` | ERROR | attempt, max_attempts, error |
| `waha_send_dead_letter` | ERROR | event_id, group_id |
| `session_disconnected` | ERROR | session_id, state |
| `watchdog_check` | INFO | session_id, status |
| `group_binding_created` | INFO | group_id, rental_id |
| `rental_inactive` | INFO | rental_id, status |

> **Rule:** Every log entry MUST have `correlation_id`. Pass it from webhook → queue job kwargs → worker → all service calls. This is the primary debugging thread.

---

## Notes for Pi Collaboration

- **Good Pi tasks:** Task 6.2, 6.3, 6.4, 6.5 (frontend impl), Task 3.2 (context builder unit tests), Task 3.3 (role compiler tests).
- **Bad Pi tasks:** Anything touching Docker Compose, Caddy, `.env`, database migrations, WAHA session management, or deploy scripts.
- **Mandatory Hermes final review:** Epic 0 (infra), Epic 2 (event pipeline), Epic 4 (watchdog), Task 7.1 (secrets), Task 7.4 (integration test).
