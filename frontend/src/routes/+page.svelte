<script lang="ts">
	import StaffCard from '$lib/components/StaffCard.svelte';
	import BottomNav from '$lib/components/BottomNav.svelte';
	import ChatBubble from '$lib/components/ChatBubble.svelte';

	export let data;
	let searchQuery = '';
	let searchResults: any[] = [];
	let searchSuggestions: any[] = [];
	let searchMessage = '';
	let isSearching = false;
	let hasSearched = false;

	// Local filter for initial display
	$: filteredStaff = data.staff?.filter((s: any) =>
		s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
		s.specialty.toLowerCase().includes(searchQuery.toLowerCase())
	) || [];

	async function handleSearch() {
		if (!searchQuery.trim() || searchQuery.trim().length < 3) return;
		isSearching = true;
		hasSearched = true;
		try {
			const res = await fetch('/api/search', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ query: searchQuery })
			});
			const result = await res.json();
			searchResults = result.results || [];
			searchSuggestions = result.suggestions || [];
			searchMessage = result.message || '';
		} catch (e) {
			searchMessage = 'Gagal memproses pencarian.';
			searchResults = [];
		}
		isSearching = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') handleSearch();
	}

	function resetSearch() {
		searchQuery = '';
		searchResults = [];
		searchSuggestions = [];
		searchMessage = '';
		hasSearched = false;
	}
</script>

<div class="min-h-screen bg-gray-50 pb-20">
	<!-- Navbar -->
	<nav class="sticky top-0 bg-white/80 backdrop-blur-md z-40 border-b border-gray-100 px-4 py-3 flex justify-between items-center">
		<div class="flex items-center gap-3">
			<button class="p-1 text-gray-600"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg></button>
			<h1 class="text-xl font-extrabold text-primary tracking-tight">SewaStaff <span class="text-gray-900">AI</span></h1>
		</div>
		<div class="flex items-center gap-3">
			<button class="relative p-1 text-gray-600">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
				<span class="absolute top-0 right-0 w-2 h-2 bg-red-500 rounded-full"></span>
			</button>
			<div class="w-8 h-8 rounded-full bg-gray-200 overflow-hidden"><img src="https://ui-avatars.com/api/?name=User&background=random" alt="User" class="w-full h-full object-cover"></div>
		</div>
	</nav>

	<main>
		<!-- Hero -->
		<section class="px-4 py-8 bg-white">
			<h2 class="text-3xl font-black text-gray-900 leading-tight mb-4">Sewa Staff AI.<br><span class="text-primary">Bantu kerja tim Anda</span><br>di WhatsApp.</h2>
			<p class="text-gray-600 mb-8">Pekerjakan staff AI cerdas untuk sales, CS, HR, dan operasional. Langsung gabung ke grup WhatsApp tim Anda.</p>
			
			<div class="bg-gray-50 rounded-xl p-4 border border-gray-100 shadow-inner mb-6 relative">
				<div class="absolute -top-3 left-4 bg-white px-2 text-xs font-bold text-gray-500 border border-gray-100 rounded-full">Grup: Tim Marketing</div>
				<div class="mt-2 space-y-3">
					<ChatBubble isUser={true} message="Tolong buatkan draft promo weekend ini ya." />
					<ChatBubble isUser={false} avatarEmoji="👩🏻‍💻" message="Tentu! Berikut draft promo diskon 20% untuk weekend ini:\n\n*🎉 PROMO WEEKEND SERU 🎉*\nDapatkan diskon 20% untuk semua produk..." />
				</div>
			</div>
		</section>

		<!-- Search -->
		<section class="px-4 py-6 sticky top-[60px] bg-gray-50/95 backdrop-blur z-30">
			<div class="relative">
				<input
					type="text"
					bind:value={searchQuery}
					on:keydown={handleKeydown}
					placeholder="Cari staff AI yang kamu butuh..."
					class="w-full pl-10 pr-12 py-3 rounded-full border border-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
				/>
				<svg class="absolute left-4 top-3.5 text-gray-400" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
				{#if hasSearched}
					<button on:click={resetSearch} class="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600 p-1">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
					</button>
				{:else}
					<button on:click={handleSearch} class="absolute right-3 top-2.5 text-primary hover:text-primary-dark p-1" disabled={isSearching}>
						{#if isSearching}
							<svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
						{:else}
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"></path><path d="M12 5l7 7-7 7"></path></svg>
						{/if}
					</button>
				{/if}
			</div>
		</section>

		<!-- Results -->
		<section class="px-4 pb-8">
			{#if hasSearched}
				<h3 class="font-bold text-gray-900 mb-4 text-lg">Hasil Pencarian</h3>
				{#if isSearching}
					<div class="text-center py-10 text-gray-500">
						<svg class="animate-spin mx-auto mb-2" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
						Mencari...
					</div>
				{:else if searchResults.length > 0}
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
						{#each searchResults as staff}
							<StaffCard {...staff} />
						{/each}
					</div>
			{:else}
				<div class="text-center py-10">
					<div class="text-4xl mb-3">🔍</div>
					<p class="text-gray-600 font-medium mb-2">{searchMessage}</p>
					{#if searchSuggestions.length > 0}
						<div class="mt-6 text-left">
							<p class="text-sm font-semibold text-gray-500 mb-3">💡 Role dengan kemampuan mirip:</p>
							<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
								{#each searchSuggestions as s}
									<div class="bg-white border border-gray-200 rounded-xl p-4 flex gap-3 hover:shadow-md transition-shadow cursor-pointer">
										<div class="text-3xl">{s.avatar_emoji || '🤖'}</div>
										<div class="flex-1 min-w-0">
											<h4 class="font-bold text-gray-900 truncate">{s.name}</h4>
											<p class="text-sm text-gray-500">{s.specialty}</p>
											<span class="inline-block mt-1 text-xs bg-amber-100 text-amber-700 rounded-full px-2 py-0.5">{s.match_reason || 'role serupa'}</span>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{:else}
						<p class="text-gray-400 text-sm">Coba kata kunci lain atau jelaskan kebutuhan staff AI kamu.</p>
					{/if}
				</div>
			{/if}
			{:else}
				<h3 class="font-bold text-gray-900 mb-4 text-lg">Staff Tersedia</h3>
				{#if filteredStaff.length === 0}
					<div class="text-center py-10 text-gray-500">Tidak ada staff yang cocok.</div>
				{:else}
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
						{#each filteredStaff as staff}
							<StaffCard {...staff} />
						{/each}
					</div>
				{/if}
			{/if}
		</section>

		<!-- Trust / USP -->
		<section class="px-4 py-8 bg-white border-y border-gray-100">
			<div class="flex overflow-x-auto gap-4 pb-4 snap-x hide-scrollbar">
				{#each ['24/7 Tersedia', 'Paham Bahasa Indonesia', 'Balas Hitungan Detik', 'Bisa Custom Knowledge'] as usp}
					<div class="snap-center shrink-0 bg-primary-light/30 rounded-lg px-4 py-3 flex items-center gap-2 border border-primary-light">
						<span class="text-primary font-bold">✓</span>
						<span class="text-sm font-medium text-gray-800">{usp}</span>
					</div>
				{/each}
			</div>
		</section>

		<!-- CTA -->
		<section class="p-4">
			<div class="bg-gradient-to-r from-primary to-primary-dark rounded-2xl p-6 text-white text-center shadow-lg relative overflow-hidden">
				<div class="absolute -right-6 -top-6 w-24 h-24 bg-white/10 rounded-full blur-xl"></div>
				<h3 class="text-xl font-bold mb-2">Butuh Staff Khusus?</h3>
				<p class="text-primary-light text-sm mb-4">Cari aja di atas — kalau belum ada, kami buatkan!</p>
				<button class="bg-white text-primary font-bold w-full py-3 rounded-xl hover:bg-gray-50 transition-colors">Coba Staff AI Gratis</button>
			</div>
		</section>
	</main>

	<BottomNav />
</div>

<style>
	.hide-scrollbar::-webkit-scrollbar { display: none; }
	.hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
