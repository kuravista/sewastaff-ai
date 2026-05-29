# SewaStaff AI — WhatsApp-Native AI Staff for Indonesian SMBs

> **SaaS platform** untuk menyewa staf virtual berbasis AI yang bekerja langsung di dalam grup WhatsApp bisnis.

## Quick Links

| Resource | URL |
|----------|-----|
| Admin Dashboard | https://sewastaffai.wuz.web.id/admin |
| DB Viewer (CloudBeaver) | https://db.wuz.web.id |
| Source Code | `/openclaw/hermes/agents/sunday/projects/sewastaff-ai/` |
| Runtime (Server 2) | `openclaw-support:/opt/sewastaff-ai/` |

## Tech Stack

- **Backend:** FastAPI (Python 3.12)
- **Frontend:** SvelteKit
- **Database:** PostgreSQL 16 + pgvector
- **Cache:** Redis 7
- **WhatsApp:** WAHA GoWS (WebSocket)
- **AI:** OpenRouter (Gemini 2.5 Flash + GPT-4o-mini fallback)
- **Embedding:** text-embedding-3-small (1536 dim)
- **Containers:** Docker Compose

## Features

- ✅ WhatsApp-native interaction (no separate app)
- ✅ Long-term memory with semantic search (pgvector RAG)
- ✅ Finance tracking (income/expense/transfer + categories)
- ✅ Reminder system (one-time + recurring)
- ✅ 5 staff templates (HR, PA, Akuntansi, CS, Sales)
- ✅ Custom personality per role via admin dashboard
- ✅ Multi-tenant architecture
- ✅ Media handling (image analysis, receipt OCR)
- ✅ Minus balance warning

## Quick Start

### Prerequisites
- Docker + Docker Compose on target server
- WAHA instance running (GoWS engine)
- OpenRouter API key

### Deploy
```bash
# 1. Clone/sync source to server
rsync -az ./ openclaw-support:/opt/sewastaff-ai/

# 2. Configure .env
cp .env.example .env
# Edit: POSTGRES_*, WAHA_*, OPENROUTER_API_KEY, etc.

# 3. Build and start
docker compose -f docker-compose.prod.yml up -d --build

# 4. Verify
docker compose -f docker-compose.prod.yml logs -f worker
```

### ⚠️ Important: Deploy Rule
**ALWAYS use `--build`** when deploying code changes. `docker compose restart` does NOT update files inside the container.

```bash
# ✅ Correct
docker compose -f docker-compose.prod.yml up -d --build worker

# ❌ Wrong — code won't update
docker compose -f docker-compose.prod.yml restart worker
```

## Documentation Index

| File | Description |
|------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture, data flow, message pipeline |
| [DATABASE.md](DATABASE.md) | Schema, pgvector, tables reference |
| [API.md](API.md) | Backend API endpoints |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deploy workflow, server setup, troubleshooting |
| [BUSINESS.md](BUSINESS.md) | Business model, pricing, target market |
| [PROMPTS.md](PROMPTS.md) | Role prompt engineering, customization guide |

## Staff Templates

| Slug | Name | Specialty | Price/month |
|------|------|-----------|-------------|
| hr | Mbak Sera | HR & Rekrutmen | Rp99.000 |
| pa | Mas Dika | Personal Assistant | Rp79.000 |
| akuntansi | Mbak Rini | Keuangan & Akuntansi | Rp99.000 |
| cs | Kak Aldi | Customer Service | Rp79.000 |
| sales | Mas Rio | Sales Follow-up | Rp99.000 |
