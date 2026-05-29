# API Reference

Base URL: `https://sewastaffai.wuz.web.id` (production)

All admin endpoints require authentication via `X-Admin-Token` header or Caddy Basic Auth.

## Authentication

Admin endpoints use a shared secret:

```text
X-Admin-Token: sewastaff-admin-2026
```

Or Caddy Basic Auth on the `/admin` route.

---

## System Stats

### GET /api/admin/system/stats

Returns system overview.

```json
{
  "rentals": 1,
  "memories": 38,
  "reminders": 4,
  "messages": 125
}
```

---

## Rentals

### GET /api/admin/rentals

List all rental instances.

```json
[
  {
    "id": "982b4e78-d9f4-4d2e-be70-be4ad0318461",
    "tenant_id": "...",
    "template_id": "52c67339-...",
    "custom_traits": {
      "staff_name": "Simpatiku",
      "bisnis_name": "Test Bisnis",
      "bisnis_desc": "...",
      "produk_jasa": "...",
      "jam_operasional": "08:00-17:00",
      "faq": [{"q": "...", "a": "..."}]
    },
    "status": "active",
    "started_at": "2026-05-28T...",
    "expires_at": "2026-06-28T..."
  }
]
```

### PUT /api/admin/rentals/{rental_id}/traits

Update business info (traits) for a rental.

```json
{
  "bisnis_name": "Toko Sejahtera",
  "bisnis_desc": "Toko kelontong lengkap",
  "produk_jasa": "Sembako, minuman, snack",
  "jam_operasional": "06:00-22:00",
  "faq": [
    {"q": "Ada delivery?", "a": "Ya, radius 3km gratis."}
  ]
}
```

### PUT /api/admin/rentals/{rental_id}/status

Update rental status.

```json
{"status": "active"}
```

---

## Staff Templates

### GET /api/admin/templates

List all staff templates with their prompts.

```json
[
  {
    "id": "52c67339-...",
    "slug": "hr",
    "name": "Mbak Sera",
    "specialty": "HR & Rekrutmen",
    "base_prompt": "Role:\nKamu adalah Mbak Sera...",
    "avatar_emoji": "👩‍💼",
    "price_monthly_idr": 99000,
    "is_active": true
  }
]
```

### PUT /api/admin/templates/{template_id}

Update template including custom prompt.

```json
{
  "base_prompt": "Role:\nKamu adalah Mbak Sera, staf HR yang galak...",
  "is_active": true
}
```

Changes take effect immediately — no redeploy needed. The `role_compiler.py` reads `base_prompt` from DB at query time.

---

## Memory

### GET /api/admin/memory/{rental_id}

List extracted memories for a rental.

```json
[
  {
    "id": "1b032bb4-...",
    "rental_id": "982b4e78-...",
    "type": "fact",
    "content": "Shalat Dhuha jam 8 besok",
    "source": "chat_extraction",
    "confidence": 0.9,
    "created_at": "2026-05-29T00:30:00Z"
  }
]
```

### DELETE /api/admin/memory/{memory_id}

Delete a specific memory.

```json
{"deleted": "1b032bb4-..."}
```

---

## Knowledge Base

### GET /api/admin/knowledge/{rental_id}

List knowledge items.

### POST /api/admin/knowledge/{rental_id}

Add knowledge item.

```json
{
  "type": "product",
  "content": "Produk X harga Rp50.000, garansi 1 tahun.",
  "source_url": "https://..."
}
```

### PUT /api/admin/knowledge/{knowledge_id}/status

Update knowledge status (active/pending).

### DELETE /api/admin/knowledge/{knowledge_id}

Delete knowledge item.

---

## WAHA Proxy

### GET /api/admin/waha/sessions

List WhatsApp sessions.

### POST /api/admin/waha/sessions/{name}/start

Start a WhatsApp session.

### POST /api/admin/waha/sessions/{name}/stop

Stop a WhatsApp session.

### POST /api/admin/waha/sessions/{name}/logout

Logout (disconnect phone number).

---

## Group Bindings

### POST /api/admin/bindings

Bind a WhatsApp group to a rental.

```json
{
  "group_id": "120363426757842154@g.us",
  "rental_id": "982b4e78-d9f4-4d2e-be70-be4ad0318461"
}
```

### DELETE /api/admin/bindings/{group_id}

Unbind a group.

---

## Reminders

### GET /api/admin/reminders/{rental_id}

List reminders for a rental.

### DELETE /api/admin/reminders/{reminder_id}

Cancel/delete a reminder.
