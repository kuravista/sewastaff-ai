<script lang="ts">
	import { page } from '$app/stores';
	import { getStaffBySlug } from '$lib/api';
	import { onMount } from 'svelte';

	const staffId = $page.params.id;
	let staff: any = null;
	let loading = true;

	const fallback: Record<string, any> = {
		'staff-cs': {
			slug: 'staff-cs', name: 'Rara - CS Pro', specialty: 'Customer Service', avatarEmoji: '👩🏻‍💼',
			features: ['Balas komplain otomatis', 'Follow-up pelanggan', 'Template respon profesional', 'Monitoring kepuasan pelanggan'],
			priceMonthlyIdr: 299000, isCustom: false,
			description: 'Staff CS AI terbaik untuk bisnis Anda. Rara siap balas pesan pelanggan 24/7, menangani komplain, dan menjaga kepuasan pelanggan secara otomatis di grup WhatsApp.'
		}
	};

	onMount(async () => {
		try {
			staff = await getStaffBySlug(staffId);
		} catch {
			staff = fallback[staffId] || null;
		}
		loading = false;
	});

	const formatPrice = (price: number) => new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(price);
</script>

<div class="min-h-screen bg-white">
	<nav class="sticky top-0 z-40 bg-white border-b border-gray-100 px-4 py-4 flex items-center gap-3">
		<a href="/" class="text-gray-600"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg></a>
		<h1 class="font-bold text-gray-900">Detail Staff</h1>
	</nav>

	{#if loading}
		<div class="flex justify-center py-20"><div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div></div>
	{:else if staff}
		<div class="px-4 py-8 max-w-lg mx-auto">
			<div class="bg-primary-light rounded-2xl p-6 text-center mb-8">
				<div class="text-5xl mb-3">{staff.avatarEmoji}</div>
				<h2 class="text-2xl font-bold text-gray-900">{staff.name}</h2>
				<span class="inline-block text-primary bg-white font-semibold text-sm px-3 py-1 rounded-full mt-2">{staff.specialty}</span>
			</div>

			<h3 class="font-bold text-gray-900 mb-4">Kemampuan Staff</h3>
			<ul class="space-y-3 mb-8">
				{#each staff.features as feature}
					<li class="flex items-start gap-3">
						<div class="w-5 h-5 bg-primary-light rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
							<span class="text-primary text-xs">✓</span>
						</div>
						<span class="text-gray-700">{feature}</span>
					</li>
				{/each}
			</ul>

			{#if staff.description}
				<p class="text-gray-600 text-sm mb-8 bg-gray-50 p-4 rounded-xl leading-relaxed">{staff.description}</p>
			{/if}

			<div class="border border-gray-100 rounded-xl p-4 mb-8 flex justify-between items-center">
				<div>
					<p class="text-sm text-gray-500">Harga Bulanan</p>
					<p class="text-2xl font-bold text-gray-900">{formatPrice(staff.priceMonthlyIdr)}</p>
				</div>
				<span class="text-xs text-green-600 bg-green-50 font-medium px-3 py-1 rounded-full">Tersedia</span>
			</div>

			<div class="grid grid-cols-2 gap-3">
				<a href="/try/{staff.slug}" class="text-center py-3 border-2 border-primary text-primary font-bold rounded-xl hover:bg-primary-light transition-colors">Coba Gratis</a>
				<a href="/sewa/{staff.slug}" class="text-center py-3 bg-primary text-white font-bold rounded-xl hover:bg-primary-dark transition-colors">Sewa Sekarang</a>
			</div>
		</div>
	{:else}
		<div class="text-center py-20 text-gray-500">Staff tidak ditemukan.</div>
	{/if}
</div>