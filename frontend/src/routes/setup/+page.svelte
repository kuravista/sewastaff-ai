<script lang="ts">
	import { page } from '$app/stores';
	import { onDestroy, onMount } from 'svelte';
	import { getRental, getBinding, bindGroup } from '$lib/api';

	const rentalId = $page.url.searchParams.get('rental') || '';

	let staffName = 'Staff AI';
	let staffEmoji = '🤖';
	let loading = true;
	let error = '';

	// Binding state
	let bindingStatus: 'unbound' | 'pending' | 'active' | 'disabled' = 'unbound';
	let groupName = '';
	let inviteLink = '';
	let submitting = false;
	let poller: ReturnType<typeof setInterval> | null = null;

	onMount(async () => {
		if (!rentalId) {
			error = 'Rental ID tidak ditemukan. Silakan sewa staff terlebih dahulu.';
			loading = false;
			return;
		}

		try {
			const rental = await getRental(rentalId);
			staffName = rental.staff_name || 'Staff AI';
			staffEmoji = rental.staff_emoji || '🤖';
		} catch {
			error = 'Rental tidak ditemukan.';
			loading = false;
			return;
		}

		// Check existing binding
		try {
			const binding = await getBinding(rentalId);
			bindingStatus = binding.status || 'unbound';
			groupName = binding.group_name || '';
			inviteLink = binding.invite_link || '';

			if (bindingStatus === 'pending') {
				startPolling();
			}
		} catch {
			// No binding yet — that's fine
		}

		loading = false;
	});

	function startPolling() {
		if (poller) clearInterval(poller);
		poller = setInterval(async () => {
			try {
				const binding = await getBinding(rentalId);
				bindingStatus = binding.status || 'unbound';
				groupName = binding.group_name || '';

				if (bindingStatus === 'active') {
					stopPolling();
				}
			} catch {
				// keep polling
			}
		}, 3000);
	}

	function stopPolling() {
		if (poller) {
			clearInterval(poller);
			poller = null;
		}
	}

	async function handleSubmit() {
		if (!inviteLink.trim()) return;
		submitting = true;
		error = '';

		try {
			const result = await bindGroup(rentalId, inviteLink.trim());
			bindingStatus = result.status || 'pending';
			groupName = result.group_name || '';

			if (bindingStatus === 'pending') {
				startPolling();
			}
		} catch (e: any) {
			error = 'Gagal menghubungkan bot ke group. Pastikan link invite valid.';
		}

		submitting = false;
	}

	onDestroy(() => stopPolling());
</script>

<div class="min-h-screen bg-gray-50">
	<!-- Header -->
	<nav class="sticky top-0 z-40 bg-white border-b border-gray-100 px-4 py-4 flex items-center gap-3">
		<a href="/" class="text-gray-600">
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<polyline points="15 18 9 12 15 6"></polyline>
			</svg>
		</a>
		<h1 class="font-bold text-gray-900">Setup WhatsApp</h1>
	</nav>

	<div class="px-4 py-6 max-w-lg mx-auto">
		{#if loading}
			<div class="flex justify-center py-20">
				<div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
			</div>
		{:else if error && !rentalId}
			<div class="bg-white rounded-2xl p-8 text-center shadow-sm border border-gray-100">
				<div class="text-4xl mb-3">😕</div>
				<h2 class="text-xl font-bold text-gray-900 mb-2">Oops!</h2>
				<p class="text-gray-600 mb-6">{error}</p>
				<a href="/" class="block w-full py-3 bg-primary text-white font-bold rounded-xl">Kembali ke Beranda</a>
			</div>
		{:else}
			<!-- Staff info card -->
			<div class="bg-primary-light rounded-2xl p-5 text-center mb-6">
				<div class="text-4xl mb-2">{staffEmoji}</div>
				<h2 class="text-lg font-bold text-gray-900">{staffName}</h2>
				<p class="text-sm text-gray-600">Staff AI kamu sudah siap!</p>
			</div>

			{#if bindingStatus === 'active'}
				<!-- Success state -->
				<div class="bg-white rounded-2xl p-8 text-center shadow-sm border border-gray-100">
					<div class="text-5xl mb-4">✅</div>
					<h2 class="text-2xl font-black text-gray-900 mb-2">Bot Sudah Aktif!</h2>
					{#if groupName}
						<p class="text-gray-600 mb-4">Bot <strong>{staffName}</strong> sudah aktif di group <strong>{groupName}</strong></p>
					{:else}
						<p class="text-gray-600 mb-4">Bot <strong>{staffName}</strong> sudah terhubung ke group WhatsApp kamu!</p>
					{/if}
					<p class="text-sm text-gray-500 mb-6">Sekarang kamu bisa mulai chat dengan {staffName} di group WhatsApp.</p>
					<a href="/" class="block w-full py-3 bg-primary text-white font-bold rounded-xl">Kembali ke Beranda</a>
				</div>
			{:else if bindingStatus === 'pending'}
				<!-- Pending state -->
				<div class="bg-white rounded-2xl p-8 text-center shadow-sm border border-gray-100 mb-4">
					<div class="flex justify-center mb-4">
						<div class="w-12 h-12 border-3 border-primary border-t-transparent rounded-full animate-spin"></div>
					</div>
					<h2 class="text-xl font-bold text-gray-900 mb-2">Menunggu Bot Masuk ke Group...</h2>
					<p class="text-gray-600 mb-4">Bot sedang bergabung ke group WhatsApp kamu. Ini biasanya memakan waktu beberapa detik.</p>
					<p class="text-sm text-gray-400">Auto-check setiap 3 detik...</p>
				</div>
			{:else}
				<!-- Setup guide (unbound) -->
				<div class="space-y-4">
					<!-- Step 1 -->
					<div class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
						<div class="flex items-center gap-3 mb-3">
							<div class="w-8 h-8 bg-primary rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0">1</div>
							<h3 class="font-bold text-gray-900">Buat Group WhatsApp Baru</h3>
						</div>
						<ol class="text-sm text-gray-600 space-y-2 pl-11">
							<li>• Buka WhatsApp, buat group baru</li>
							<li>• Tambahkan anggota tim kamu</li>
							<li>• <strong>Jangan lupa</strong> — siapkan link invite group</li>
						</ol>
					<div class="mt-3 ml-11">
						<button onclick={() => {
							const guide = document.getElementById('invite-guide');
							if (guide) guide.classList.toggle('hidden');
						}} class="text-primary text-sm font-semibold">Cara ambil link invite →</button>
							<div id="invite-guide" class="hidden mt-2 bg-gray-50 rounded-xl p-3 text-xs text-gray-600 space-y-1">
								<p>1. Buka group WhatsApp</p>
								<p>2. Tap nama group di atas</p>
								<p>3. Scroll ke bawah, tap <strong>"Undang via link"</strong></p>
								<p>4. Salin link yang muncul</p>
							</div>
						</div>
					</div>

					<!-- Step 2 -->
					<div class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
						<div class="flex items-center gap-3 mb-3">
							<div class="w-8 h-8 bg-primary rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0">2</div>
							<h3 class="font-bold text-gray-900">Paste Link Invite Group</h3>
						</div>
						<div class="pl-11 space-y-3">
							<input
								type="url"
								bind:value={inviteLink}
								placeholder="https://chat.whatsapp.com/xxxxx"
								class="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
							/>
							<button
								onclick={handleSubmit}
								disabled={!inviteLink.trim() || submitting}
								class="w-full py-3 bg-primary text-white font-bold rounded-xl hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
							>
								{#if submitting}
									<span class="flex items-center justify-center gap-2">
										<span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
										Menghubungkan...
									</span>
								{:else}
									Hubungkan Bot ke Group
								{/if}
							</button>
							{#if error}
								<p class="text-red-500 text-sm">{error}</p>
							{/if}
						</div>
					</div>

					<!-- Step 3 (preview) -->
					<div class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
						<div class="flex items-center gap-3">
							<div class="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-gray-400 font-bold text-sm flex-shrink-0">3</div>
							<h3 class="font-bold text-gray-400">Bot Aktif di Group</h3>
						</div>
						<p class="text-sm text-gray-400 pl-11 mt-2">Setelah bot masuk, {staffName} akan langsung bisa membantu tim kamu di group.</p>
					</div>
				</div>
			{/if}
		{/if}
	</div>
</div>
