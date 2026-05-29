# Business Model

## Vision

**SewaStaff AI** adalah platform SaaS yang menyewakan staf virtual berbasis AI yang bekerja langsung di dalam grup WhatsApp bisnis. Tidak perlu download app, tidak perlu training — langsung pakai di chat yang sudah ada.

## Problem Statement

UMKM Indonesia (50+ juta bisnis) menghadapi:

1. **SDM mahal** — Gaji staff admin/HR/CS minimum Rp3-5 juta/bulan
2. **Turnover tinggi** — Staff kerja 3-6 bulan lalu resign
3. **Operasional bottleneck** — Pemilik bisnis mengerjakan semuanya sendiri
4. **WhatsApp-centric** — Semua bisnis kecil menjalankan operasional via WA group

## Solution

SewaStaff AI menawarkan staf AI yang:

- **Langsung tinggal di grup WA** — Zero friction, no app install
- **24/7 aktif** — Tidak cuti, tidak tidur, tidak resign
- **Harga terjangkau** — Mulai Rp79.000/bulan
- **Bisa di-custom** — Personality dan knowledge bisa diatur pemilik
- **Punya memori jangka panjang** — Ingat preferensi pelanggan, data bisnis, SOP

## Target Market

### Primary: UMKM Indonesia

- Toko kelontong, warung, restoran kecil
- Online shop / reseller (Shopee, Tokopedia, IG Shop)
- Jasa service (bengkel, laundry, salon)
- Klinik/apotek kecil
- Startup kecil yang belum punya team HR/admin

### Secondary: Freelancer & Solopreneur

- Konsultan, desainer, developer
- Coach, trainer, guru les
- Agent properti, asuransi

## Staff Templates & Pricing

| Template | Name | Specialty | Price/month |
|----------|------|-----------|-------------|
| HR | Mbak Sera | HR & Rekrutmen | Rp99.000 |
| PA | Mas Dika | Personal Assistant | Rp79.000 |
| Akuntansi | Mbak Rini | Keuangan & Akuntansi | Rp99.000 |
| CS | Kak Aldi | Customer Service | Rp79.000 |
| Sales | Mas Rio | Sales Follow-up | Rp99.000 |

## Core Features

### Finance Tracking (Semua Role)
- Catat pemasukan/pengeluaran via chat: "Beli bensin 50rb"
- Query saldo: "Sisa saldo" / "Rekap keuangan"
- Kategori otomatis (Makanan, Kendaraan, dll)
- Warning jika saldo minus
- Laporan: harian, mingguan, bulanan

### Reminder System (Semua Role)
- Set reminder: "Ingatkan rapat besok jam 10"
- Recurring: "Setiap hari jam 5 ingatkan shalat"
- List/cancel: "Daftar reminder" / "Batalin reminder minum obat"
- Natural language: "5 menit lagi ingetin sarapan"

### Long-Term Memory
- Fakta otomatis diekstrak dari percakapan
- Semantic search via pgvector (pencarian berbasis makna)
- Identity memory (selalu diinject: preferensi owner, SOP, rules)
- Knowledge base (upload info produk, FAQ, kebijakan)

### Custom Personality
- Setiap role bisa di-custom prompt-nya via admin dashboard
- Inject nama bisnis, produk, jam operasional, FAQ
- Atur tone, sapaan, gaya bicara

## Onboarding Flow

1. User kunjungi website → pilih staff template
2. Bayar subscription (akan integrasi payment gateway)
3. User invite bot ke grup WA bisnis
4. Bot auto-detect dan mulai bekerja
5. User isi info bisnis via admin dashboard
6. Bot mulai melayani dengan konteks bisnis yang tepat

## Revenue Model

### Subscription
- Per staff per bulan
- Rp79.000–99.000 tergantung role
- Discount untuk multi-staff (bundle)

### Potential Upsell
- Custom domain/white-label
- Advanced analytics dashboard
- API access for integration
- Premium LLM tier (Claude, GPT-4)

## Competitive Advantage

| Competitor | Weakness | Our Advantage |
|------------|----------|---------------|
| Generic chatbot (ChatGPT) | Terpisah dari WA, no memory | Native WA, persistent memory |
| Chatbot builder (ManyChat) | No AI intelligence, rule-based | AI-powered with RAG memory |
| Human VA | Mahal, turnover, jam terbatas | 24/7, Rp79k/bulan, no turnover |
| Enterprise AI (Intercom) | Mahal, complex setup | Simple, WA-native, affordable |

## Roadmap

### Phase 1 — MVP (Current)
- [x] 5 staff templates
- [x] WhatsApp integration via WAHA
- [x] Finance tracking
- [x] Reminder system (one-time + recurring)
- [x] Long-term memory with pgvector
- [x] Admin dashboard
- [x] Custom prompts per role

### Phase 2 — Growth
- [ ] Payment integration (Midtrans/Xendit)
- [ ] User self-service onboarding
- [ ] Multi-staff bundle pricing
- [ ] Analytics dashboard (spend patterns, chat volume)
- [ ] Chat summary feature
- [ ] Knowledge base upload (PDF, URL)

### Phase 3 — Scale
- [ ] Multi-language (English support)
- [ ] Voice message support
- [ ] Integration dengan Shopee/Tokopedia API
- [ ] Team collaboration (multi-user admin)
- [ ] Mobile app untuk admin
- [ ] Marketplace template (community-built roles)

## Success Metrics

| Metric | Target (3 bulan) | Target (6 bulan) |
|--------|-------------------|-------------------|
| Active rentals | 50 | 200 |
| Monthly recurring revenue | Rp5M | Rp20M |
| Messages processed/day | 500 | 5.000 |
| Memory accuracy | 80% | 90% |
| Customer retention | 70% | 80% |
