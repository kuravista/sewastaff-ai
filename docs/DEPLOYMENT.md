# Deployment Guide

## Server Architecture

| Server | Role | Host |
|--------|------|------|
| Server 1 (openclaw) | Source code, development | Local |
| Server 2 (openclaw-support) | Runtime, production | `ubuntu@168.110.215.139` |

## Deploy Path

```text
Source:  /openclaw/hermes/agents/sunday/projects/sewastaff-ai/
Runtime: /opt/sewastaff-ai/ (on Server 2)
```

## Docker Services (docker-compose.prod.yml)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| app | Custom (FastAPI) | 127.0.0.1:8020 | REST API |
| worker | Custom (Python) | — | WAHA WebSocket listener |
| frontend | Custom (SvelteKit) | 127.0.0.1:3020 | Admin dashboard |
| postgres | pgvector/pgvector:pg16 | — (internal) | Database |
| redis | redis:7-alpine | — (internal) | Cache |

External service on shared Docker network (`app_default`):
- `app-waha-1` (WAHA GoWS) on port 3000

## Deploy Workflow

### Standard Deploy (code change)

```bash
# From Server 1
cd /openclaw/hermes/agents/sunday/projects/sewastaff-ai/

# 1. Sync changed files
rsync -az backend/app/services/myservice.py openclaw-support:/opt/sewastaff-ai/backend/app/services/

# 2. Rebuild and restart worker
ssh openclaw-support 'cd /opt/sewastaff-ai && sudo docker compose -f docker-compose.prod.yml up -d --build worker'
```

### ⚠️ Critical: Always Rebuild

```bash
# ✅ Correct — rebuilds image with new code
docker compose -f docker-compose.prod.yml up -d --build worker

# ❌ Wrong — restarts old image, code changes ignored
docker compose -f docker-compose.prod.yml restart worker
```

Docker copies source files at build time (`COPY . .` in Dockerfile). A restart only restarts the existing image.

### Full Rebuild (clean slate)

```bash
ssh openclaw-support 'cd /opt/sewastaff-ai && \
  sudo docker compose -f docker-compose.prod.yml down && \
  sudo docker compose -f docker-compose.prod.yml build --no-cache && \
  sudo docker compose -f docker-compose.prod.yml up -d'
```

### Frontend-only Deploy

```bash
rsync -az frontend/ openclaw-support:/opt/sewastaff-ai/frontend/
ssh openclaw-support 'cd /opt/sewastaff-ai && sudo docker compose -f docker-compose.prod.yml up -d --build frontend'
```

## Database Access

### CloudBeaver (Web UI)

URL: https://db.wuz.web.id

Connection details:
- Host: `sewastaff-ai-postgres-1`
- Port: `5432`
- Database: `sewastaff`
- Username: `sewastaff`
- Password: `SwSt2026Pr0d!`

The postgres container is connected to `app_default` Docker network alongside CloudBeaver.

### CLI (from Server 2)

```bash
sudo docker exec sewastaff-ai-postgres-1 psql -U sewastaff -d sewastaff
```

## Caddy Configuration

Served via Caddy reverse proxy on Server 2:

```text
sewastaffai.wuz.web.id {
    reverse_proxy /api/* localhost:8020
    reverse_proxy /* localhost:3020
}
```

Admin routes are protected by Caddy Basic Auth.

## Environment Variables (.env)

```text
# Postgres
POSTGRES_USER=sewastaff
POSTGRES_PASSWORD=<password>
POSTGRES_DB=sewastaff
DATABASE_URL=postgresql+asyncpg://sewastaff:<password>@postgres:5432/sewastaff

# Redis
REDIS_URL=redis://redis:6379/0

# WAHA
WAHA_BASE_URL=http://app-waha-1:3000
WAHA_API_KEY=<key>
WAHA_SESSION_IDS=default

# OpenRouter
OPENROUTER_API_KEY=sk-or-...

# App
APP_ENV=production
APP_SECRET_KEY=<secret>
```

## Troubleshooting

### Worker not responding to messages

```bash
# Check if worker is running
ssh openclaw-support 'sudo docker compose -f /opt/sewastaff-ai/docker-compose.prod.yml ps'

# Check worker logs
ssh openclaw-support 'sudo docker logs --since=10m sewastaff-ai-worker-1'

# Common issues:
# - WAHA WebSocket disconnected → restart worker
# - LLM API errors → check OpenRouter key/quota
# - DB connection errors → check postgres container
```

### pgvector DatatypeMismatchError

ORM models declare embedding columns as `String` but DB expects `vector(1536)`. All vector writes must use raw SQL with explicit CAST:

```python
await db.execute(sa_text(
    "... CAST(:emb AS vector) ..."
), {"emb": str(embedding_vector)})
```

### Code changes not taking effect

You forgot `--build`. Rebuild the container:

```bash
ssh openclaw-support 'cd /opt/sewastaff-ai && sudo docker compose -f docker-compose.prod.yml up -d --build worker'
```

### Verify code inside container

```bash
ssh openclaw-support 'sudo docker exec sewastaff-ai-worker-1 cat /app/app/services/myservice.py | head -20'
```

### Check container networks

```bash
ssh openclaw-support 'sudo docker inspect sewastaff-ai-postgres-1 --format "{{json .NetworkSettings.Networks}}"'
```

## Useful Commands

```bash
# Tail worker logs
ssh openclaw-support 'sudo docker logs -f --since=5m sewastaff-ai-worker-1'

# Check postgres tables
ssh openclaw-support 'sudo docker exec sewastaff-ai-postgres-1 psql -U sewastaff -d sewastaff -c "\dt"'

# Check active reminders
ssh openclaw-support 'sudo docker exec sewastaff-ai-postgres-1 psql -U sewastaff -d sewastaff -c "SELECT title, trigger_at, status FROM reminders WHERE status='\''pending'\'';"'

# Count memories with embeddings
ssh openclaw-support 'sudo docker exec sewastaff-ai-postgres-1 psql -U sewastaff -d sewastaff -c "SELECT COUNT(*) as total, COUNT(embedding) as with_emb FROM staff_memories;"'
```
