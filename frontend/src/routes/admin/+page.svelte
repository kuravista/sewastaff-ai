<script lang="ts">
  import { onMount } from 'svelte';
  import { adminApi } from '$lib/adminApi';

  type Faq = { q: string; a: string };
  type Traits = { bisnis_name?: string; bisnis_desc?: string; produk_jasa?: string; jam_operasional?: string; faq?: Faq[] };
  type Rental = {
    id: string;
    status?: string;
    custom_traits?: Traits;
    tenant?: { email?: string; name?: string };
    template?: { slug?: string; name?: string; specialty?: string; avatar_emoji?: string };
    is_bound?: boolean;
    group_binding?: { group_id?: string; group_name?: string };
    memory_count?: number;
    knowledge_count?: number;
    memories?: MemoryItem[];
    knowledge?: KnowledgeItem[];
    created_at?: string;
    group_id?: string;
  };
  type Template = { id: string; slug?: string; name?: string; specialty?: string; base_prompt?: string; avatar_emoji?: string; price_monthly_idr?: number; is_active?: boolean };
  type MemoryItem = { id: string; type?: string; content?: string; source?: string; confidence?: number; created_at?: string };
  type KnowledgeItem = { id: string; type?: string; source_url?: string; content?: string; summary?: string; status?: string; created_at?: string };
  type Stats = { total_rentals?: number; active_rentals?: number; total_memories?: number; total_knowledge_items?: number };

  const ADMIN_TOKEN = 'sewastaff-admin-2026';
  let activeTab = 'rentals';
  let modalTab = 'knowledge';
  let stats: Stats = {};
  let rentals: Rental[] = [];
  let templates: Template[] = [];
  let selectedRental: Rental | null = null;
  let selectedMemories: MemoryItem[] = [];
  let selectedKnowledge: KnowledgeItem[] = [];
  let traitsForm: Traits = { faq: [] };
  let loading = true;
  let modalLoading = false;
  let error = '';
  let saving = '';
  let editingTemplateId = '';
  let templateForm: Template | null = null;
  let knowledgeType = 'text';
  let knowledgeContent = '';
  let knowledgeUrl = '';
  let tokenReveal = false;

  // Chat history state
  type ChatMessage = { event_id: string; sender_id?: string; content?: string; is_from_me: boolean; message_type?: string; timestamp?: string };
  let chatMessages: ChatMessage[] = [];
  let chatLoading = false;

  // Reminder state
  type ReminderItem = { id: string; title: string; description?: string; fire_at: string; status: string; recurrence?: string; created_by: string; created_at: string; sent_at?: string };
  let reminders: ReminderItem[] = [];
  let reminderLoading = false;

  // WAHA state
  type WahaSession = { name: string; status: string; me?: { id?: string; name?: string; pushName?: string } | null; engine?: any };
  let wahaSessions: WahaSession[] = [];
  let wahaQrBase64 = '';
  let wahaPairCode = '';
  let wahaPairPhone = '';
  let wahaLoading = false;
  let wahaPollTimer = 0;
  let wahaQrVisible = false;

  // Role Requests state
  type RoleRequest = {
    cluster_id: string; representative_query: string; query_count: number;
    unique_users: number; status: string; suggested_slug?: string;
    suggested_name?: string; suggested_specialty?: string;
    generated_prompt?: string; created_template_id?: string;
    sample_queries: string[];
  };
  let roleRequests: RoleRequest[] = [];
  let roleRequestsLoading = false;
  let roleRequestsError = '';
  let generatingId = '';
  let approvingId = '';

  async function loadRoleRequests() {
    roleRequestsLoading = true;
    roleRequestsError = '';
    try {
      roleRequests = await adminApi.getRoleRequests();
    } catch (e) {
      roleRequestsError = 'Gagal memuat role requests.';
    } finally {
      roleRequestsLoading = false;
    }
  }

  async function generateDraft(clusterId: string) {
    generatingId = clusterId;
    try {
      await adminApi.generateRoleDraft(clusterId);
      roleRequests = await adminApi.getRoleRequests();
    } catch (e) {
      roleRequestsError = 'Gagal generate draft.';
    } finally {
      generatingId = '';
    }
  }

  async function approveRequest(clusterId: string) {
    approvingId = clusterId;
    try {
      await adminApi.approveRoleRequest(clusterId);
      roleRequests = await adminApi.getRoleRequests();
      templates = await adminApi.getTemplates();
    } catch (e) {
      roleRequestsError = 'Gagal approve.';
    } finally {
      approvingId = '';
    }
  }

  async function rejectRequest(clusterId: string) {
    try {
      await adminApi.rejectRoleRequest(clusterId);
      roleRequests = await adminApi.getRoleRequests();
    } catch (e) {
      roleRequestsError = 'Gagal reject.';
    }
  }

  onMount(loadAll);

  async function loadAll() {
    loading = true;
    error = '';
    try {
      const [s, r, t] = await Promise.all([adminApi.getStats(), adminApi.getRentals(), adminApi.getTemplates()]);
      stats = s || {};
      rentals = Array.isArray(r) ? r : [];
      templates = Array.isArray(t) ? t : [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Gagal memuat data admin.';
    } finally {
      loading = false;
    }
  }

  async function openRental(rental: Rental) {
    selectedRental = rental;
    modalTab = 'knowledge';
    modalLoading = true;
    knowledgeType = 'text';
    knowledgeContent = '';
    knowledgeUrl = '';
    chatMessages = [];
    reminders = [];
    try {
      const [detail, memories, knowledge] = await Promise.all([
        adminApi.getRental(rental.id),
        adminApi.getMemory(rental.id),
        adminApi.getKnowledge(rental.id)
      ]);
      selectedRental = { ...rental, ...(detail || {}) };
      selectedMemories = Array.isArray(memories) ? memories : (detail?.memories || []);
      selectedKnowledge = Array.isArray(knowledge) ? knowledge : (detail?.knowledge || []);
      const traits = selectedRental?.custom_traits || {};
      traitsForm = { ...traits, faq: Array.isArray(traits.faq) ? traits.faq.map((f) => ({ ...f })) : [] };
    } catch (e) {
      error = e instanceof Error ? e.message : 'Gagal memuat detail rental.';
    } finally {
      modalLoading = false;
    }
  }

  function closeModal() { selectedRental = null; }
  function stop(e: MouseEvent) { e.stopPropagation(); }
  const money = (n?: number) => new Intl.NumberFormat('id-ID').format(n || 0);
  const dateFmt = (d?: string) => d ? new Date(d).toLocaleString('id-ID') : '-';
  const statusClass = (s?: string) => s === 'active' ? 'bg-green-100 text-green-700' : s === 'suspended' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700';

  async function saveTraits() {
    if (!selectedRental) return;
    saving = 'traits';
    try {
      const updated = await adminApi.updateTraits(selectedRental.id, traitsForm);
      selectedRental = { ...selectedRental, custom_traits: updated?.custom_traits || traitsForm };
      await loadAll();
    } finally { saving = ''; }
  }

  async function changeStatus(status: string) {
    if (!selectedRental) return;
    saving = 'status';
    try {
      await adminApi.updateStatus(selectedRental.id, status);
      selectedRental = { ...selectedRental, status };
      await loadAll();
    } finally { saving = ''; }
  }

  async function addKnowledge() {
    if (!selectedRental) return;
    saving = 'knowledge';
    const data = knowledgeType === 'link' ? { type: 'link', source_url: knowledgeUrl } : { type: 'text', content: knowledgeContent };
    try {
      await adminApi.addKnowledge(selectedRental.id, data);
      selectedKnowledge = await adminApi.getKnowledge(selectedRental.id);
      knowledgeContent = '';
      knowledgeUrl = '';
      await loadAll();
    } finally { saving = ''; }
  }

  async function setKnowledgeStatus(id: string, status: string) {
    await adminApi.approveKnowledge(id, status);
    if (selectedRental) selectedKnowledge = await adminApi.getKnowledge(selectedRental.id);
  }
  async function removeKnowledge(id: string) {
    await adminApi.deleteKnowledge(id);
    selectedKnowledge = selectedKnowledge.filter((k) => k.id !== id);
  }
  async function removeMemory(id: string) {
    await adminApi.deleteMemory(id);
    selectedMemories = selectedMemories.filter((m) => m.id !== id);
  }

  async function loadChat() {
    if (!selectedRental) return;
    chatLoading = true;
    try {
      chatMessages = await adminApi.getMessages(selectedRental.id);
    } catch (e) {
      chatMessages = [];
    } finally {
      chatLoading = false;
    }
  }

  async function loadReminders() {
    if (!selectedRental) return;
    reminderLoading = true;
    try {
      reminders = await adminApi.getReminders(selectedRental.id);
    } catch (e) {
      reminders = [];
    } finally {
      reminderLoading = false;
    }
  }

  async function cancelReminder(id: string) {
    try {
      await adminApi.deleteReminder(id);
      reminders = reminders.filter((r) => r.id !== id);
    } catch (e) {
      error = 'Gagal menghapus reminder.';
    }
  }
  function addFaq() { traitsForm.faq = [...(traitsForm.faq || []), { q: '', a: '' }]; }
  function removeFaq(i: number) { traitsForm.faq = (traitsForm.faq || []).filter((_, idx) => idx !== i); }
  function editTemplate(t: Template) { editingTemplateId = t.id; templateForm = { ...t }; }
  async function saveTemplate() {
    if (!templateForm) return;
    saving = 'template';
    try {
      await adminApi.updateTemplate(templateForm.id, templateForm);
      editingTemplateId = '';
      templateForm = null;
      templates = await adminApi.getTemplates();
    } finally { saving = ''; }
  }

  // WAHA functions
  async function loadWaha() {
    wahaLoading = true;
    try {
      wahaSessions = await adminApi.wahaSessions();
      wahaQrBase64 = '';
      wahaPairCode = '';
      // Auto-show QR if session in SCAN_QR_CODE
      const sess = wahaSessions.find(s => s.status === 'SCAN_QR_CODE');
      if (sess && !wahaQrBase64) showQr(sess.name);
    } catch (e) { error = 'Gagal memuat WAHA sessions'; }
    finally { wahaLoading = false; }
  }

  function startWahaPoll() {
    stopWahaPoll();
    wahaPollTimer = window.setInterval(async () => {
      try {
        wahaSessions = await adminApi.wahaSessions();
        const sess = wahaSessions[0];
        if (sess?.status === 'WORKING' || sess?.status === 'CONNECTED') {
          // QR scanned successfully — stop polling, refresh
          stopWahaPoll();
          wahaQrBase64 = '';
          wahaQrVisible = false;
        } else if (sess?.status === 'SCAN_QR_CODE' && !wahaQrBase64) {
          showQr(sess.name);
        }
      } catch (e) {}
    }, 5000);
  }

  function stopWahaPoll() {
    if (wahaPollTimer) { clearInterval(wahaPollTimer); wahaPollTimer = 0; }
  }

  async function startWahaSession(name: string) {
    wahaLoading = true;
    try {
      await adminApi.wahaStart(name);
      await new Promise(r => setTimeout(r, 3000));
      await loadWaha();
      startWahaPoll();
    } finally { wahaLoading = false; }
  }

  async function stopWahaSession(name: string) {
    wahaLoading = true;
    try {
      await adminApi.wahaStop(name);
      await new Promise(r => setTimeout(r, 2000));
      await loadWaha();
    } finally { wahaLoading = false; }
  }

  async function logoutWahaSession(name: string) {
    if (!confirm(`Logout session "${name}"? Kamu harus scan QR ulang untuk menghubungkan kembali.`)) return;
    wahaLoading = true;
    stopWahaPoll();
    try {
      await adminApi.wahaLogout(name);
      await new Promise(r => setTimeout(r, 2000));
      wahaQrBase64 = '';
      wahaQrVisible = false;
      await loadWaha();
    } finally { wahaLoading = false; }
  }

  async function showQr(name: string) {
    wahaLoading = true;
    wahaQrBase64 = '';
    try {
      const data = await adminApi.wahaQr(name);
      if (data.qr_base64) {
        wahaQrBase64 = data.qr_base64;
        wahaQrVisible = true;
        startWahaPoll();
      }
      else error = data.error || 'QR tidak tersedia. Coba start session dulu.';
    } catch (e) { error = 'Gagal mengambil QR'; }
    finally { wahaLoading = false; }
  }

  async function regenerateQr(name: string) {
    wahaQrBase64 = '';
    wahaLoading = true;
    try {
      // Logout + restart to get fresh QR
      await adminApi.wahaLogout(name);
      await new Promise(r => setTimeout(r, 1500));
      await adminApi.wahaStart(name);
      await new Promise(r => setTimeout(r, 3000));
      const data = await adminApi.wahaQr(name);
      if (data.qr_base64) {
        wahaQrBase64 = data.qr_base64;
        wahaQrVisible = true;
        startWahaPoll();
      } else {
        error = data.error || 'Gagal regenerate QR';
      }
    } catch (e) { error = 'Gagal regenerate QR'; }
    finally { wahaLoading = false; }
  }

  async function requestCode(name: string) {
    if (!wahaPairPhone.trim()) return;
    wahaLoading = true;
    wahaPairCode = '';
    try {
      const data = await adminApi.wahaRequestCode(name, wahaPairPhone.trim());
      wahaPairCode = data.code || 'Gagal mendapatkan kode';
    } catch (e) { error = 'Gagal request pairing code'; }
    finally { wahaLoading = false; }
  }

  async function deleteWahaSession(name: string) {
    if (!confirm(`Hapus session "${name}"? Data login WhatsApp akan hilang.`)) return;
    wahaLoading = true;
    stopWahaPoll();
    try {
      await adminApi.wahaDelete(name);
      await new Promise(r => setTimeout(r, 1000));
      wahaQrBase64 = '';
      wahaQrVisible = false;
      await loadWaha();
    } finally { wahaLoading = false; }
  }

  function wahaStatusClass(s: string) {
    if (s === 'SCAN_QR_CODE') return 'bg-amber-100 text-amber-700';
    if (s === 'STARTING') return 'bg-blue-100 text-blue-700';
    if (s === 'WORKING' || s === 'CONNECTED') return 'bg-green-100 text-green-700';
    return 'bg-slate-100 text-slate-700';
  }

</script>

<svelte:head><title>SewaStaff Admin</title></svelte:head>

<div class="min-h-screen bg-white text-slate-900">
  <header class="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between">
      <h1 class="text-2xl font-bold">🤖 SewaStaff Admin</h1>
      <div class="flex flex-wrap gap-2 text-sm">
        <span class="rounded-full bg-purple-50 px-3 py-1 text-purple-700">Rentals: {stats.total_rentals || 0}</span>
        <span class="rounded-full bg-green-50 px-3 py-1 text-green-700">Active: {stats.active_rentals || 0}</span>
        <span class="rounded-full bg-slate-100 px-3 py-1">Memory: {stats.total_memories || 0}</span>
        <span class="rounded-full bg-slate-100 px-3 py-1">Knowledge: {stats.total_knowledge_items || 0}</span>
      </div>
    </div>
    <nav class="mx-auto flex max-w-7xl gap-2 px-4 pb-3">
      {#each [['rentals','Rentals & Tenants'], ['prompts','Staff Prompts'], ['role-requests','Role Requests'], ['whatsapp','WhatsApp / WAHA'], ['system','System']] as tab}
        <button class="rounded-xl px-4 py-2 text-sm font-semibold {activeTab === tab[0] ? 'bg-[var(--color-primary)] text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}" on:click={() => { activeTab = tab[0]; if (tab[0] === 'whatsapp') loadWaha(); if (tab[0] === 'role-requests') loadRoleRequests(); }}>{tab[1]}</button>
      {/each}
    </nav>
  </header>

  <main class="mx-auto max-w-7xl px-4 py-6">
    {#if error}<div class="mb-4 rounded-xl bg-red-50 p-4 text-red-700">{error}</div>{/if}
    {#if loading}<div class="rounded-2xl border p-8 text-center text-slate-500">Memuat admin dashboard...</div>{/if}

    {#if !loading && activeTab === 'rentals'}
      <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {#each rentals as rental}
          <article class="rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md">
            <div class="flex gap-3">
              <div class="text-4xl">{rental.template?.avatar_emoji || '🤖'}</div>
              <div class="min-w-0 flex-1">
                <h2 class="truncate text-lg font-bold">{rental.custom_traits?.bisnis_name || rental.tenant?.name || 'Tanpa Nama Bisnis'}</h2>
                <p class="text-sm text-slate-600">Staff: {rental.template?.name || '-'} ({rental.template?.specialty || rental.template?.slug || '-'})</p>
                <p class="mt-1 text-sm">Status: <span class="rounded-full px-2 py-1 text-xs font-semibold {statusClass(rental.status)}">{rental.status || 'trial'}</span></p>
              </div>
            </div>
            <div class="mt-4 space-y-2 text-sm text-slate-700">
              <p>Email: {rental.tenant?.email || '-'}</p>
              <p>Group WA: {rental.is_bound ? `✅ ${rental.group_binding?.group_name || rental.group_binding?.group_id || 'Terhubung'}` : '❌ Belum'}</p>
              <p>Memory: {rental.memory_count || 0} items · Knowledge: {rental.knowledge_count || 0} items</p>
            </div>
            <button class="mt-4 w-full rounded-xl bg-[var(--color-primary)] px-4 py-2 font-semibold text-white" on:click={() => openRental(rental)}>Kelola</button>
          </article>
        {/each}
      </section>
    {/if}

    {#if !loading && activeTab === 'prompts'}
      <section class="space-y-4">
        {#each templates as t}
          <article class="rounded-2xl border p-5 shadow-sm">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div><h2 class="text-xl font-bold">{t.avatar_emoji || '🤖'} {t.name} - {t.specialty}</h2><p class="text-slate-600">Rp {money(t.price_monthly_idr)}/bulan</p></div>
              <button class="rounded-xl bg-slate-900 px-4 py-2 text-white" on:click={() => editTemplate(t)}>Edit</button>
            </div>
            {#if editingTemplateId === t.id && templateForm}
              <div class="mt-5 grid gap-3">
                <div class="grid gap-3 md:grid-cols-4"><input class="input" bind:value={templateForm.name} placeholder="Name" /><input class="input" bind:value={templateForm.specialty} placeholder="Specialty" /><input class="input" bind:value={templateForm.avatar_emoji} placeholder="Emoji" /><input class="input" type="number" bind:value={templateForm.price_monthly_idr} placeholder="Price" /></div>
                <textarea class="input min-h-72 font-mono text-sm" bind:value={templateForm.base_prompt}></textarea>
                <p class="rounded-xl bg-purple-50 p-3 text-sm text-purple-700">Prompt tip: Gunakan {'{bisnis_name}'}, {'{specialty}'}, {'{staff_name}'} sebagai placeholder. Tambahkan instruksi kepribadian: gunakan emoji, panggil user dengan Kak, dll.</p>
                <label class="flex items-center gap-2"><input type="checkbox" bind:checked={templateForm.is_active} /> Aktif</label>
                <button class="w-fit rounded-xl bg-[var(--color-primary)] px-5 py-2 font-semibold text-white" on:click={saveTemplate}>{saving === 'template' ? 'Menyimpan...' : 'Simpan'}</button>
              </div>
            {/if}
          </article>
        {/each}
      </section>
    {/if}

    {#if !loading && activeTab === 'role-requests'}
      <section class="space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-bold">🔮 Role Requests (Demand-Driven)</h2>
          <button class="rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold hover:bg-slate-200" on:click={loadRoleRequests}>🔄 Refresh</button>
        </div>
        {#if roleRequestsLoading}<p class="text-center text-slate-500 py-8">Memuat...</p>{/if}
        {#if roleRequestsError}<div class="rounded-xl bg-red-50 p-4 text-red-700">{roleRequestsError}</div>{/if}
        {#if !roleRequestsLoading && roleRequests.length === 0}
          <div class="rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center text-slate-500">
            <p class="text-3xl mb-2">📭</p>
            <p>Belum ada role request. User search akan otomatis tercatat di sini setelah mencapai 5 unique search.</p>
          </div>
        {/if}
        {#each roleRequests as req}
          <article class="rounded-2xl border p-5 shadow-sm">
            <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-3 mb-2">
                  <h3 class="text-lg font-bold">"{req.representative_query}"</h3>
                  <span class="rounded-full px-3 py-1 text-xs font-semibold {req.status === 'pending_review' ? 'bg-amber-100 text-amber-700' : req.status === 'auto_created' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}">
                    {req.status === 'pending_review' ? '⏳ Menunggu Review' : req.status === 'auto_created' ? '🤖 Auto Created' : '✅ Approved'}
                  </span>
                </div>
                <p class="text-sm text-slate-600 mb-2">
                  <b>{req.query_count}</b> total search · <b>{req.unique_users}</b> unique users
                </p>
                <div class="flex flex-wrap gap-1">
                  {#each req.sample_queries as sq}
                    <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{sq}</span>
                  {/each}
                </div>
                {#if req.generated_prompt}
                  <div class="mt-3 rounded-xl bg-slate-50 p-3">
                    <p class="text-sm font-semibold">{req.suggested_name || '-'} · {req.suggested_specialty || '-'}</p>
                    <details class="mt-1">
                      <summary class="text-xs text-slate-500 cursor-pointer">Lihat prompt</summary>
                      <pre class="mt-2 text-xs text-slate-700 whitespace-pre-wrap">{req.generated_prompt}</pre>
                    </details>
                  </div>
                {/if}
              </div>
              <div class="flex flex-wrap gap-2 mt-2 md:mt-0">
                {#if req.status === 'pending_review' && !req.generated_prompt}
                  <button class="rounded-xl bg-purple-600 px-4 py-2 text-sm text-white" disabled={generatingId === req.cluster_id} on:click={() => generateDraft(req.cluster_id)}>
                    {generatingId === req.cluster_id ? 'Generating...' : '🪄 Generate Draft'}
                  </button>
                {/if}
                {#if req.generated_prompt && req.status !== 'approved'}
                  <button class="rounded-xl bg-green-600 px-4 py-2 text-sm text-white" disabled={approvingId === req.cluster_id} on:click={() => approveRequest(req.cluster_id)}>
                    {approvingId === req.cluster_id ? 'Publishing...' : '✅ Approve & Publish'}
                  </button>
                {/if}
                {#if req.status === 'pending_review'}
                  <button class="rounded-xl bg-red-100 px-4 py-2 text-sm text-red-700" on:click={() => rejectRequest(req.cluster_id)}>❌ Reject</button>
                {/if}
              </div>
            </div>
          </article>
        {/each}
        <div class="rounded-2xl bg-amber-50 p-5 text-sm text-amber-900">
          <h3 class="font-bold mb-2">ℹ️ Cara Kerja</h3>
          <ul class="list-disc space-y-1 pl-5">
            <li>User search di homepage otomatis dicatat dan di-cluster berdasarkan kemiripan makna (pgvector)</li>
            <li><b>5+ unique users</b> → muncul di sini untuk direview admin</li>
            <li><b>50+ unique users</b> → otomatis dibuat tanpa review admin</li>
            <li>Klik "Generate Draft" → AI bikin profil staff (nama, prompt, harga) berdasarkan data search</li>
            <li>Setelah approve, role baru langsung muncul di homepage</li>
          </ul>
        </div>
      </section>
    {/if}

    {#if !loading && activeTab === 'whatsapp'}
      <section class="space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-bold">📱 WhatsApp Sessions</h2>
          <button class="rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold hover:bg-slate-200" on:click={loadWaha}>🔄 Refresh</button>
        </div>
        {#if wahaLoading}<p class="text-center text-slate-500 py-8">Memuat...</p>{/if}
        {#if !wahaLoading && wahaSessions.length === 0}<p class="text-center text-slate-500 py-8">Tidak ada session WAHA. Mulai session pertama.</p>{/if}
        {#each wahaSessions as s}
          <article class="rounded-2xl border p-5 shadow-sm">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div class="flex items-center gap-3">
                  <h3 class="text-lg font-bold">{s.name}</h3>
                  <span class="rounded-full px-3 py-1 text-xs font-semibold {wahaStatusClass(s.status)}">{s.status}</span>
                </div>
                {#if s.me?.pushName || s.me?.name}
                  <p class="mt-1 text-sm text-slate-600">👤 {s.me?.pushName || s.me?.name || '-'} ({s.me?.id || '-'})</p>
                {/if}
              </div>
              <div class="flex flex-wrap gap-2">
                {#if s.status === 'STOPPED' || s.status === 'FAILED'}
                  <button class="rounded-xl bg-green-600 px-4 py-2 text-sm text-white" on:click={() => startWahaSession(s.name)}>▶️ Start</button>
                {/if}
                {#if s.status === 'SCAN_QR_CODE'}
                  <button class="rounded-xl bg-purple-600 px-4 py-2 text-sm text-white" on:click={() => showQr(s.name)}>📷 QR Code</button>
                {/if}
                {#if s.status === 'WORKING' || s.status === 'CONNECTED'}
                  <button class="rounded-xl bg-amber-600 px-4 py-2 text-sm text-white" on:click={() => stopWahaSession(s.name)}>⏹️ Stop</button>
                {/if}
                <button class="rounded-xl bg-red-600 px-4 py-2 text-sm text-white" on:click={() => logoutWahaSession(s.name)}>🚪 Logout</button>
              </div>
            </div>
          </article>
        {/each}

        {#if wahaQrBase64}
          <div class="mt-4 rounded-2xl border-2 border-dashed border-purple-300 bg-white p-6 text-center">
            <h3 class="mb-4 text-lg font-bold">📷 Scan QR Code</h3>
            <img src={wahaQrBase64} alt="WhatsApp QR Code" class="mx-auto w-64 h-64" />
            <p class="mt-4 text-sm text-slate-600">Buka WhatsApp → Perangkat Tertaut → Tautkan Perangkat → Scan QR di atas</p>
            <button class="mt-4 rounded-xl bg-purple-600 px-5 py-2 text-sm text-white" on:click={() => regenerateQr('default')}>🔄 Regenerate QR Code</button>
          </div>
        {/if}

        <div class="mt-4 rounded-2xl border p-5">
          <h3 class="mb-3 font-bold">🔑 Pairing Code (Alternatif QR)</h3>
          <div class="flex flex-col gap-3 md:flex-row md:items-end">
            <div class="flex-1">
              <label class="text-sm text-slate-600">Nomor HP (tanpa +)</label>
              <input class="input mt-1" bind:value={wahaPairPhone} placeholder="6281234567890" />
            </div>
            <button class="rounded-xl bg-purple-600 px-5 py-2 text-white" on:click={() => requestCode('default')}>Minta Kode</button>
          </div>
          {#if wahaPairCode}
            <div class="mt-4 rounded-xl bg-green-50 p-4 text-center">
              <p class="text-sm text-slate-600">Masukkan kode ini di WhatsApp:</p>
              <p class="mt-2 text-3xl font-bold tracking-widest text-green-700">{wahaPairCode}</p>
            </div>
          {/if}
        </div>

        <div class="rounded-2xl bg-slate-50 p-5 text-sm text-slate-600">
          <h3 class="mb-2 font-bold text-slate-900">ℹ️ Panduan</h3>
          <ul class="list-disc space-y-1 pl-5">
            <li>Start session → tunggu status jadi SCAN_QR_CODE → scan QR atau minta pairing code</li>
            <li>Setelah QR berhasil scan, halaman auto-refresh ke status WORKING</li>
            <li>Logout = hapus login WhatsApp, harus scan QR ulang untuk reconnect</li>
            <li>Stop = disconnect sementara (bisa start lagi), Hapus = hapus session total</li>
            <li>QR expired? Klik "🔄 Regenerate QR Code" untuk dapat QR baru</li>
            <li>Gunakan nomor HP cadangan untuk testing, BUKAN nomor pribadi utama</li>
          </ul>
        </div>
      </section>
    {/if}

    {#if !loading && activeTab === 'system'}
      <section class="space-y-6">
        <div class="grid gap-4 md:grid-cols-4">
          <div class="stat"><b>{stats.total_rentals || 0}</b><span>Total Rentals</span></div><div class="stat"><b>{stats.active_rentals || 0}</b><span>Active Rentals</span></div><div class="stat"><b>{stats.total_memories || 0}</b><span>Total Memories</span></div><div class="stat"><b>{stats.total_knowledge_items || 0}</b><span>Total Knowledge</span></div>
        </div>
        <div class="rounded-2xl bg-purple-50 p-5 text-purple-900"><h2 class="font-bold">💡 Tips Memory & Knowledge:</h2><ul class="mt-2 list-disc space-y-1 pl-5"><li>Tambahkan knowledge base dulu sebelum aktifkan ke WA</li><li>AI akan otomatis ingat nama, preferensi, keluhan pelanggan</li><li>Hapus memory yang tidak relevan untuk jaga kualitas</li><li>Link ke katalog produk/Tokopedia/Shopee bisa di-extract</li></ul></div>
        <div class="rounded-2xl border p-5 text-sm text-slate-600"><b class="text-slate-900">Security:</b> Halaman admin dilindungi Caddy Basic Auth. API admin tidak expose token di frontend.</div>
      </section>
    {/if}
  </main>
</div>

{#if selectedRental}
  <div class="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-4" on:click={closeModal} role="button" tabindex="0">
    <div class="mx-auto max-w-5xl rounded-2xl bg-white p-5 shadow-2xl" on:click={stop} role="dialog" aria-modal="true">
      <div class="flex items-start justify-between gap-4"><div><h2 class="text-2xl font-bold">{selectedRental.custom_traits?.bisnis_name || 'Kelola Rental'}</h2><p class="text-sm text-slate-500">{selectedRental.id}</p></div><button class="text-2xl" on:click={closeModal}>×</button></div>
      <div class="mt-4 flex flex-wrap gap-2">{#each [['knowledge','Knowledge Base'], ['memory','Memory'], ['chat','💬 Chat History'], ['reminders','⏰ Reminder'], ['profile','Edit Profil Bisnis'], ['status','Status & Info']] as tab}<button class="rounded-xl px-3 py-2 text-sm font-semibold {modalTab === tab[0] ? 'bg-[var(--color-primary)] text-white' : 'bg-slate-100'}" on:click={() => { modalTab = tab[0]; if (tab[0] === 'chat') loadChat(); if (tab[0] === 'reminders') loadReminders(); }}>{tab[1]}</button>{/each}</div>
      {#if modalLoading}<p class="p-8 text-center text-slate-500">Memuat detail...</p>{/if}
      {#if !modalLoading && modalTab === 'knowledge'}
        <div class="mt-5 space-y-3">
          {#each selectedKnowledge as k}<div class="rounded-xl border p-4"><div class="flex flex-wrap items-center gap-2"><span class="badge">{k.type}</span><span class="badge {statusClass(k.status)}">{k.status || 'pending'}</span><button class="ml-auto text-sm text-green-700" on:click={() => setKnowledgeStatus(k.id, 'approved')}>Approve</button><button class="text-sm text-amber-700" on:click={() => setKnowledgeStatus(k.id, 'rejected')}>Reject</button><button class="text-sm text-red-700" on:click={() => removeKnowledge(k.id)}>Delete</button></div><p class="mt-2 font-medium">{k.summary || k.content || k.source_url}</p><p class="text-xs text-slate-500">{dateFmt(k.created_at)}</p></div>{/each}
          <div class="rounded-2xl bg-slate-50 p-4"><div class="flex gap-4"><label><input type="radio" bind:group={knowledgeType} value="text" /> Teks</label><label><input type="radio" bind:group={knowledgeType} value="link" /> Link</label></div>{#if knowledgeType === 'text'}<textarea class="input mt-3 min-h-28" bind:value={knowledgeContent} placeholder="Isi knowledge..."></textarea>{:else}<input class="input mt-3" bind:value={knowledgeUrl} placeholder="https://..." />{/if}<button class="mt-3 rounded-xl bg-[var(--color-primary)] px-4 py-2 font-semibold text-white" on:click={addKnowledge}>{saving === 'knowledge' ? 'Memproses...' : 'Tambah & Proses'}</button><p class="mt-3 text-sm text-slate-600">Rekomendasikan isi: produk + harga, FAQ kompleks, kebijakan return, kontak darurat, katalog gambar</p></div>
        </div>
      {/if}
      {#if !modalLoading && modalTab === 'memory'}
        <div class="mt-5 space-y-3">{#if selectedMemories.length === 0}<p class="rounded-xl bg-slate-50 p-6 text-center text-slate-500">Belum ada memory. Memory terbentuk otomatis saat pelanggan chat.</p>{/if}{#each selectedMemories as m}<div class="rounded-xl border p-4"><div class="flex gap-2"><span class="badge">{m.type}</span><button class="ml-auto text-sm text-red-700" on:click={() => removeMemory(m.id)}>Delete</button></div><p class="mt-2">{m.content}</p><div class="mt-3 h-2 rounded-full bg-slate-100"><div class="h-2 rounded-full bg-[var(--color-primary)]" style={`width:${Math.round((m.confidence || 0) * 100)}%`}></div></div><p class="mt-2 text-xs text-slate-500">{m.source || '-'} · {dateFmt(m.created_at)}</p></div>{/each}</div>
      {/if}
      {#if !modalLoading && modalTab === 'chat'}
        <div class="mt-5">
          {#if chatLoading}
            <p class="py-8 text-center text-slate-500">Memuat chat history...</p>
          {:else if chatMessages.length === 0}
            <p class="rounded-xl bg-slate-50 p-6 text-center text-slate-500">Belum ada pesan. Pesan akan muncul setelah pelanggan chat melalui WhatsApp.</p>
          {:else}
            <div class="space-y-3 max-h-[500px] overflow-y-auto pr-2">
              {#each chatMessages as msg}
                <div class="flex {msg.is_from_me ? 'justify-start' : 'justify-end'}">
                  <div class="max-w-[80%] rounded-2xl px-4 py-3 {msg.is_from_me ? 'bg-slate-100 text-slate-900 rounded-bl-md' : 'bg-blue-600 text-white rounded-br-md'}">
                    <p class="whitespace-pre-wrap text-sm">{msg.content || '<i class="opacity-60">[media/empty]</i>'}</p>
                    <p class="mt-1 text-xs {msg.is_from_me ? 'text-slate-500' : 'text-blue-200'}">{dateFmt(msg.timestamp)}{#if msg.sender_id} · {msg.sender_id}{/if}</p>
                  </div>
                </div>
              {/each}
            </div>
            <p class="mt-3 text-xs text-slate-400 text-center">{chatMessages.length} pesan terakhir</p>
          {/if}
        </div>
      {/if}
      {#if !modalLoading && modalTab === 'reminders'}
        <div class="mt-5">
          {#if reminderLoading}
            <p class="py-8 text-center text-slate-500">Memuat reminder...</p>
          {:else if reminders.length === 0}
            <p class="rounded-xl bg-slate-50 p-6 text-center text-slate-500">Belum ada reminder. User bisa set reminder via chat WhatsApp, misalnya: "ingetin besok meeting jam 9 pagi"</p>
          {:else}
            <div class="space-y-3">
              {#each reminders as r}
                <div class="rounded-xl border p-4">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="rounded-full px-2 py-1 text-xs font-semibold {r.status === 'pending' ? 'bg-amber-100 text-amber-700' : r.status === 'sent' ? 'bg-green-100 text-green-700' : r.status === 'cancelled' ? 'bg-slate-100 text-slate-500' : 'bg-red-100 text-red-700'}">{r.status}</span>
                    {#if r.recurrence}
                      <span class="rounded-full bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-700">🔄 {r.recurrence}</span>
                    {/if}
                    {#if r.status === 'pending'}
                      <button class="ml-auto rounded-lg bg-red-50 px-3 py-1 text-sm font-medium text-red-600 hover:bg-red-100" on:click={() => cancelReminder(r.id)}>Batalkan</button>
                    {/if}
                  </div>
                  <p class="mt-2 font-semibold">{r.title}</p>
                  {#if r.description}
                    <p class="mt-1 text-sm text-slate-600">{r.description}</p>
                  {/if}
                  <p class="mt-2 text-xs text-slate-500">
                    ⏰ {dateFmt(r.fire_at)} · oleh {r.created_by}
                    {#if r.sent_at} · dikirim {dateFmt(r.sent_at)}{/if}
                  </p>
                </div>
              {/each}
            </div>
            <p class="mt-3 text-xs text-slate-400 text-center">{reminders.filter(r => r.status === 'pending').length} pending · {reminders.length} total</p>
          {/if}
        </div>
      {/if}
      {#if !modalLoading && modalTab === 'profile'}
        <div class="mt-5 grid gap-3"><input class="input" bind:value={traitsForm.bisnis_name} placeholder="Nama bisnis" /><textarea class="input min-h-24" bind:value={traitsForm.bisnis_desc} placeholder="Deskripsi bisnis"></textarea><textarea class="input min-h-24" bind:value={traitsForm.produk_jasa} placeholder="Produk/jasa"></textarea><input class="input" bind:value={traitsForm.jam_operasional} placeholder="Jam operasional" /><h3 class="font-bold">FAQ</h3>{#each traitsForm.faq || [] as f, i}<div class="grid gap-2 rounded-xl border p-3 md:grid-cols-[1fr_1fr_auto]"><input class="input" bind:value={f.q} placeholder="Pertanyaan" /><input class="input" bind:value={f.a} placeholder="Jawaban" /><button class="text-red-700" on:click={() => removeFaq(i)}>Hapus</button></div>{/each}<button class="w-fit rounded-xl bg-slate-100 px-4 py-2" on:click={addFaq}>+ FAQ</button><button class="w-fit rounded-xl bg-[var(--color-primary)] px-5 py-2 font-semibold text-white" on:click={saveTraits}>{saving === 'traits' ? 'Menyimpan...' : 'Simpan Perubahan'}</button></div>
      {/if}
      {#if !modalLoading && modalTab === 'status'}
        <div class="mt-5 space-y-4"><p>Current status: <span class="rounded-full px-2 py-1 text-xs font-semibold {statusClass(selectedRental.status)}">{selectedRental.status || 'trial'}</span></p><div class="flex gap-2"><button class="rounded-xl bg-green-600 px-4 py-2 text-white" on:click={() => changeStatus('active')}>Aktifkan</button><button class="rounded-xl bg-red-600 px-4 py-2 text-white" on:click={() => changeStatus('suspended')}>Suspend</button></div><div class="rounded-xl bg-slate-50 p-4 text-sm"><p>Rental ID: {selectedRental.id}</p><p>Created: {dateFmt(selectedRental.created_at)}</p><p>Group ID: {selectedRental.group_id || (selectedRental.is_bound ? (selectedRental.group_binding?.group_name || selectedRental.group_binding?.group_id || 'Terhubung') : '-')}</p></div></div>
      {/if}
    </div>
  </div>
{/if}

<style>
  :global(.input) { @apply w-full rounded-xl border border-slate-200 px-3 py-2 outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-100; }
  :global(.badge) { @apply rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700; }
  :global(.stat) { @apply rounded-2xl border border-slate-200 p-5 shadow-sm; }
  :global(.stat b) { @apply block text-3xl text-purple-700; }
  :global(.stat span) { @apply text-sm text-slate-500; }
</style>
