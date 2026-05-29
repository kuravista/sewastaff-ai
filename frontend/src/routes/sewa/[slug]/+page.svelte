<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { createRental, getStaffBySlug } from '$lib/api';

	const slug = $page.params.slug;

	let staff: any = $state(null);
	let loading = $state(true);
	let submitting = $state(false);
	let error = $state('');
	let tenantName = $state('');
	let tenantPhone = $state('');

	const fallback: Record<string, any> = {
		'staff-cs': {
			slug: 'staff-cs',
			name: 'Rara - CS Pro',
			specialty: 'Customer Service',
			avatarEmoji: '👩🏻‍💼',
			priceMonthlyIdr: 299000,
			description: 'Staff CS AI terbaik untuk bisnis Anda.'
		}
	};

	onMount(async () => {
		try {
			staff = await getStaffBySlug(slug);
		} catch {
			staff = fallback[slug] || null;
		}
		loading = false;
	});

	const formatPrice = (price: number) => new Intl.NumberFormat('id-ID', {
		style: 'currency',
		currency: 'IDR',
		minimumFractionDigits: 0
	}).format(price || 0);

	function normalizePhone(phone: string) {
		const cleaned = phone.replace(/[^0-9]/g, '');
		if (cleaned.startsWith('0')) return `62${cleaned.slice(1)}`;
		return cleaned;
	}

	async function handleSubmit() {
		error = '';
		if (!tenantName.trim()) {
			error = 'Nama wajib diisi.';
			return;
		}
		if (!tenantPhone.trim()) {
			error = 'No. WhatsApp wajib diisi.';
			return;
		}

		submitting = true;
		try {
			const result = await createRental(slug, tenantName.trim(), normalizePhone(tenantPhone));
			const rentalId = result.rental_id || result.id;
			await goto(`/setup?rental=${rentalId}`);
		} catch {
			error = 'Gagal membuat rental. Coba lagi beberapa saat.';
			submitting = false;
		}
	}
</script>

<div class="min-h-screen bg-gray-50">
	<nav class="sticky top-0 z-40 bg-white border-b border-gray-100 px-4 py-4 flex items-center gap-3">
		<a href="/" class="text-gray-600">
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg>
		</a>
		<h1 class="font-bold text-gray-900">Sewa Staff</h1>
	</nav>

	<div class="px-4 py-6 max-w-lg mx-auto">
		{#if loading}
			<div class="flex justify-center py-20"><div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div></div>
		{:else if staff}
			<div class="bg-primary-light rounded-2xl p-6 text-center mb-6">
				<div class="text-5xl mb-3">{staff.avatarEmoji}</div>
				<h2 class="text-2xl font-bold text-gray-900">{staff.name}</h2>
				<span class="inline-block text-primary bg-white font-semibold text-sm px-3 py-1 rounded-full mt-2">{staff.specialty}</span>
			</div>

			<div class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 mb-6">
				<div class="flex justify-between items-center mb-4">
					<div>
						<p class="text-sm text-gray-500">Harga Bulanan</p>
						<p class="text-2xl font-bold text-gray-900">{formatPrice(staff.priceMonthlyIdr)}</p>
					</div>
					<span class="text-xs text-green-600 bg-green-50 font-medium px-3 py-1 rounded-full">Tersedia</span>
				</div>
				<p class="text-sm text-gray-600">Setelah sewa, kamu akan diarahkan untuk menghubungkan {staff.name} ke group WhatsApp tim kamu.</p>
			</div>

			<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 space-y-4">
				<div>
					<label for="tenant-name" class="block text-sm font-bold text-gray-900 mb-2">Nama</label>
					<input
						id="tenant-name"
						type="text"
						bind:value={tenantName}
						placeholder="Nama kamu / bisnis"
						class="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
					/>
				</div>

				<div>
					<label for="tenant-phone" class="block text-sm font-bold text-gray-900 mb-2">No. WhatsApp</label>
					<input
						id="tenant-phone"
						type="tel"
						bind:value={tenantPhone}
						placeholder="Contoh: 08123456789"
						class="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
					/>
					<p class="text-xs text-gray-500 mt-1">Nomor dipakai untuk data rental, tanpa login.</p>
				</div>

				{#if error}
					<p class="text-red-500 text-sm">{error}</p>
				{/if}

				<button
					type="submit"
					disabled={submitting}
					class="w-full py-4 bg-primary text-white font-bold rounded-xl hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
				>
					{#if submitting}
						<span class="flex items-center justify-center gap-2"><span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>Membuat Rental...</span>
					{:else}
						Sewa Sekarang
					{/if}
				</button>
			</form>
		{:else}
			<div class="bg-white rounded-2xl p-8 text-center shadow-sm border border-gray-100">
				<div class="text-4xl mb-3">😕</div>
				<h2 class="text-xl font-bold text-gray-900 mb-2">Staff Tidak Ditemukan</h2>
				<p class="text-gray-600 mb-6">Staff yang kamu cari tidak tersedia.</p>
				<a href="/" class="block w-full py-3 bg-primary text-white font-bold rounded-xl">Lihat Staff Lain</a>
			</div>
		{/if}
	</div>
</div>
