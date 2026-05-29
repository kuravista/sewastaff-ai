# PRD-lite: SewaStaff AI

## 1. Product Goal
- **What:** WhatsApp-native AI staff rental service. Owner sewa "staff virtual" yang hidup di dalam WhatsApp group.
- **Why now:** Unofficial WA API makin stabil (WAHA GoWS), Gemini Flash murah dan vision-capable, UMKM Indonesia makin butuh automasi tapi tidak mau belajar tools baru.
- **Business outcome:** Rp99k/group/bulan × N active groups. High margin (infra cost <Rp10k/group/bulan). Goal: 20 active groups di bulan ke-3 = Rp1.98jt MRR minimal viability.

---

## 2. Users

### Primary User
- **Who:** Solopreneur / online shop owner / small agency founder Indonesia. Tech-aware. Sudah pakai WA group untuk koordinasi.
- **Job to be done:** Delegasikan tugas repetitif operasional (screen CV, follow up leads, track keuangan ringan) tanpa hire staff baru.
- **Pain level:** High — langsung kehilangan uang (lost sales, slow response) atau waktu (admin drain).

### Secondary User
- **Who:** Tim kecil owner (1–3 orang). Mereka ada di group yang sama.
- **Why they matter:** Mereka yang berinteraksi langsung dengan AI staff sehari-hari. Pengalaman mereka menentukan retention.

---

## 3. Core User Journeys

### Journey 1: Onboarding & Aktivasi Staff AI
- **Trigger:** Owner buka `sewastaffai.wuz.web.id`, search "Staff HR".
- **Main flow:**
  1. Owner pilih role dari katalog (HR, PA, Sales, Reminder, Finance).
  2. Lihat preview: nama staff, tone, spesialisasi, harga.
  3. Klik "Sewa" → isi form bisnis (nama bisnis, deskripsi, FAQ dasar).
  4. Sistem generate system prompt via role compiler.
  5. Owner dapat instruksi: "Buat grup WA baru → invite nomor ini."
  6. Owner buat grup sendiri + invite nomor WAHA.
  7. Sistem deteksi group_id dari WAHA webhook → bind ke rental record.
  8. Staff AI aktif. Balas: "Halo! Saya [Nama], siap bantu [spesialisasi]. Ketik apa yang perlu dibantu."

### Journey 2: Daily Use (Owner chat dengan Staff AI)
- **Trigger:** Owner atau tim kirim pesan di grup WA.
- **Main flow:**
  1. WAHA terima pesan → webhook → FastAPI ingress.
  2. Normalize event → resolve group_id → load rental + role context.
  3. Queue per session_id → worker ambil → build context (memory + role).
  4. LLM inference (Gemini Flash).
  5. Pacing delay 3–8 detik (human-like).
  6. WAHA send reply ke group.
- **Desired outcome:** Owner merasa ada "orang" yang bantu, bukan bot.

### Journey 3: Owner kirim gambar ke Staff Finance
- **Trigger:** Owner foto struk/nota → kirim ke grup Staff Finance.
- **Main flow:**
  1. WAHA terima image → webhook dengan `media_url`.
  2. Normalize → `message_type: image`.
  3. Worker download image → inject ke Gemini Flash vision.
  4. AI baca angka/detail dari foto → catat atau rekap.
- **Desired outcome:** Owner tidak perlu ketik ulang data dari nota.

### Journey 4: Trial via Web
- **Trigger:** Owner belum mau bayar, mau test dulu.
- **Main flow:**
  1. Pilih role → klik "Coba Gratis".
  2. Chat langsung di web UI (bukan WA).
  3. Terbatas: 10 pesan / trial.
  4. Setelah limit → CTA: "Aktifkan via WhatsApp Rp99k/bulan."
- **Desired outcome:** Owner yakin produk berguna sebelum bayar.

---

## 4. MVP Scope

### In scope
- Katalog 5 role pre-built: HR, PA, Sales Follow-up, Reminder, Finance ringan.
- AI identity per role: nama, tone, spesialisasi (misal: Mbak Sera untuk HR).
- Role compiler: template role + form input bisnis → system prompt.
- WhatsApp group binding via WAHA webhook auto-detect.
- Reactive-only message handling (no broadcast).
- Image input support (Gemini vision).
- Per-session Redis queue dengan pacing delay + jitter.
- Event normalization + deduplication.
- Simple onboarding via web form.
- Trial mode via web (10 pesan, no WA).
- Billing manual: Rp99k/group/bulan via transfer/QRIS.
- Admin: Telegram alert untuk session drop + billing reminder.
- Docker Compose deploy di Server 2.
- Domain: `sewastaffai.wuz.web.id`.

### In scope but simplified
- Memory: short-term context window (last N messages per group). No long-term vector DB yet.
- Dashboard: status aktif/tidak aktif + total tagihan. No analytics.
- Multi-session WAHA: 2–3 nomor pool. Assignment manual oleh admin.

### Out of scope (Phase 2+)
- Custom role builder oleh user.
- Voice note / audio processing (STT layer).
- PDF/document parsing.
- Payment gateway otomatis.
- Proactive messaging / broadcast.
- Long-term vector memory.
- Human handoff UI.
- Multi-channel (Telegram, Discord).
- Green tick / official WA API.

---

## 5. Functional Requirements

- **FR-1 Katalog Staff:** Web UI menampilkan daftar role pre-built. User bisa search/filter. Setiap role punya nama, avatar, tone, spesialisasi, harga.
- **FR-2 Role Compiler:** Input form bisnis (nama, deskripsi, produk/jasa, FAQ, jam operasional) → generate system prompt per rental instance. Tidak freeform.
- **FR-3 Group Binding:** Sistem deteksi otomatis ketika nomor WAHA ditambah ke grup → bind `group_id` ke `rental_id` → aktifkan staff AI.
- **FR-4 Event Pipeline:** WAHA webhook → normalisasi → dedup via `event_id` → queue per `session_id` → worker → LLM → paced reply.
- **FR-5 Image Handling:** Download media dari WAHA, inject ke Gemini Flash vision endpoint, hasilkan reply berdasarkan konten gambar.
- **FR-6 Pacing:** Delay 3–8 detik (dengan random jitter) antar reply. Max 5 pesan identik/jam per session. Pause 5 menit setelah 100 pesan/sesi/jam.
- **FR-7 Fallback Reply:** Jika LLM gagal → fallback ke model kedua → jika masih gagal → "Maaf, saya sedang gangguan. Coba lagi sebentar."
- **FR-8 Media Filter:** Document/video/audio → auto reply sopan. Sticker/reaction → ignore.
- **FR-9 Trial Mode:** Web chat UI dengan limit 10 pesan. No WA required. CTA setelah limit.
- **FR-10 Session Watchdog:** Monitor WAHA session status. Jika drop → Telegram alert ke admin dalam <5 menit.
- **FR-11 Billing Tracking:** Setiap rental punya `active_since`, `expires_at`, `status`. Admin update manual. Notif Telegram H-3 sebelum expiry.

---

## 6. Non-Functional Requirements

- **Reliability:** Session watchdog max 5 menit deteksi drop. Retry queue max 3x untuk WAHA send.
- **Performance:** Median response latency <10 detik (includes pacing delay). LLM call <5 detik.
- **Security:** `.env` tidak di-commit. No secrets in logs. API endpoints rate-limited. Webhook validation. Tenant isolation strict (group hanya bisa akses rental-nya sendiri).
- **Auditability:** Structured JSON logs, `correlation_id` per event end-to-end. Message events di-log ke Postgres (tanpa konten sensitif).
- **Usability:** Onboarding <5 menit dari landing ke staff aktif di WA group.
- **Anti-ban compliance:** Semua WA-level actions wajib lewat queue per session dengan pacing. Tidak ada direct send bypass.

---

## 7. Success Criteria

- **User success:** Owner berhasil aktivasi staff AI dalam <5 menit dan mendapat reply pertama dalam 10 detik setelah pesan pertama di grup.
- **Business success:** 5 paying groups aktif di bulan ke-1. 20 paying groups di bulan ke-3.
- **Signal:** Ratio trial → paid conversion >20%. Churn di bulan pertama <30%.

---

## 8. Risks / Open Questions

- **Product risk:** Owner merasa "bot-ish" dan tidak percaya dengan AI. Mitigasi: AI identity kuat (nama + tone), pacing human-like.
- **Operational risk:** WhatsApp ban nomor WAHA. Mitigasi: pacing ketat, 2–3 nomor pool, warmup tiap nomor baru.
- **Technical risk:** WAHA session drop saat traffic. Mitigasi: watchdog + auto-alert + manual reconnect workflow.
- **Open:** Apakah WA auto-kick nomor yang baru ditambah ke banyak grup? → Perlu test dengan nomor warmup sebelum go-live.
