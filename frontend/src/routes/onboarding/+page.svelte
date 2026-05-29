<script lang="ts">
	import { onDestroy } from 'svelte';
	import { startOnboarding, getOnboardingStatus } from '$lib/api';

	let step = 1;
	let role = '';
	let bisnis = { name: '', desc: '', produk: '', jamOps: '', faqs: [{ q: '', a: '' }] };
	let errors: Record<string, string> = {};
	let rentalId = '';
	let inviteLink = '';
	let status = 'Menunggu bot masuk grup WhatsApp...';
	let poller: ReturnType<typeof setInterval> | null = null;
	const roles = ['Customer Service', 'Sales', 'HR Admin', 'Personal Assistant', 'Akuntansi', 'Custom Staff'];

	function validateStep() {
		errors = {};
		if (step === 1 && !role) errors.role = 'Pilih role staff dulu.';
		if (step === 2) {
			if (!bisnis.name.trim()) errors.name = 'Nama bisnis wajib diisi.';
			if (!bisnis.desc.trim()) errors.desc = 'Deskripsi bisnis wajib diisi.';
			if (!bisnis.produk.trim()) errors.produk = 'Produk/layanan wajib diisi.';
			if (!bisnis.jamOps.trim()) errors.jamOps = 'Jam operasional wajib diisi.';
			bisnis.faqs.forEach((faq, i) => {
				if (!faq.q.trim() || !faq.a.trim()) errors[`faq${i}`] = 'FAQ harus berisi pertanyaan dan jawaban.';
			});
		}
		return Object.keys(errors).length === 0;
	}

	function next() { if (validateStep()) step += 1; }
	function addFaq() { bisnis.faqs = [...bisnis.faqs, { q: '', a: '' }]; }
	function removeFaq(i: number) { bisnis.faqs = bisnis.faqs.filter((_, idx) => idx !== i); }

	async function submitOnboarding() {
		if (!validateStep()) return;
		try {
			const res = await startOnboarding({ role, business: bisnis });
			rentalId = res.rental_id || res.id || 'demo-rental';
			inviteLink = res.invite_link || 'https://wa.me/628000000000?text=invite';
		} catch {
			rentalId = 'demo-rental';
			inviteLink = 'https://wa.me/628000000000?text=invite';
		}
		step = 3;
		poller = setInterval(checkStatus, 5000);
	}

	async function checkStatus() {
		try {
			const res = await getOnboardingStatus(rentalId);
			status = res.status_text || res.status || status;
			if (res.status === 'success' || res.connected) {
				if (poller) clearInterval(poller);
				step = 4;
			}
		} catch {
			status = 'Masih menunggu koneksi WhatsApp...';
		}
	}

	onDestroy(() => { if (poller) clearInterval(poller); });
</script>

<div class="min-h-screen bg-gray-50 px-4 py-6">
	<div class="max-w-xl mx-auto">
		<a href="/" class="text-sm text-primary font-semibold">← Kembali</a>
		<h1 class="text-2xl font-black text-gray-900 mt-4 mb-2">Onboarding Staff AI</h1>
		<p class="text-gray-600 mb-6">Lengkapi data agar staff AI paham bisnis Anda.</p>

		<div class="flex gap-2 mb-8">
			{#each [1,2,3,4] as n}
				<div class="h-2 flex-1 rounded-full {step >= n ? 'bg-primary' : 'bg-gray-200'}"></div>
			{/each}
		</div>

		{#if step === 1}
			<div class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
				<h2 class="font-bold text-gray-900 mb-4">Pilih role staff</h2>
				<div class="grid grid-cols-2 gap-3 mb-4">
					{#each roles as r}
						<button on:click={() => role = r} class="p-4 rounded-xl border text-left font-semibold {role === r ? 'border-primary bg-primary-light text-primary' : 'border-gray-200 text-gray-700'}">{r}</button>
					{/each}
				</div>
				{#if errors.role}<p class="text-red-500 text-sm mb-3">{errors.role}</p>{/if}
				<button on:click={next} class="w-full bg-primary text-white font-bold py-3 rounded-xl">Lanjut</button>
			</div>
		{:else if step === 2}
			<div class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 space-y-4">
				<h2 class="font-bold text-gray-900">Detail bisnis</h2>
				<input bind:value={bisnis.name} placeholder="Nama bisnis" class="w-full border rounded-xl px-4 py-3" />
				{#if errors.name}<p class="text-red-500 text-xs">{errors.name}</p>{/if}
				<textarea bind:value={bisnis.desc} placeholder="Deskripsi bisnis" class="w-full border rounded-xl px-4 py-3 h-24"></textarea>
				{#if errors.desc}<p class="text-red-500 text-xs">{errors.desc}</p>{/if}
				<input bind:value={bisnis.produk} placeholder="Produk/layanan utama" class="w-full border rounded-xl px-4 py-3" />
				<input bind:value={bisnis.jamOps} placeholder="Jam operasional" class="w-full border rounded-xl px-4 py-3" />

				<h3 class="font-bold text-gray-900">FAQ</h3>
				{#each bisnis.faqs as faq, i}
					<div class="border border-gray-100 rounded-xl p-3 space-y-2">
						<input bind:value={faq.q} placeholder="Pertanyaan" class="w-full border rounded-lg px-3 py-2" />
						<input bind:value={faq.a} placeholder="Jawaban" class="w-full border rounded-lg px-3 py-2" />
						{#if bisnis.faqs.length > 1}<button on:click={() => removeFaq(i)} class="text-red-500 text-sm">Hapus FAQ</button>{/if}
						{#if errors[`faq${i}`]}<p class="text-red-500 text-xs">{errors[`faq${i}`]}</p>{/if}
					</div>
				{/each}
				<button on:click={addFaq} class="text-primary font-semibold text-sm">+ Tambah FAQ</button>
				<button on:click={submitOnboarding} class="w-full bg-primary text-white font-bold py-3 rounded-xl">Buat Staff AI</button>
			</div>
		{:else if step === 3}
			<div class="bg-white rounded-2xl p-6 text-center shadow-sm border border-gray-100">
				<div class="text-4xl mb-4">📲</div>
				<h2 class="text-xl font-bold mb-2">Undang bot ke grup WhatsApp</h2>
				<p class="text-gray-600 mb-4">Buka link berikut, pilih grup, lalu jadikan bot admin bila diminta.</p>
				<a href={inviteLink} class="block bg-primary text-white font-bold py-3 rounded-xl mb-4">Buka WhatsApp</a>
				<p class="text-sm text-gray-500">Status: {status}</p>
				<button on:click={() => step = 4} class="mt-4 text-primary font-semibold text-sm">Saya sudah undang bot</button>
			</div>
		{:else}
			<div class="bg-white rounded-2xl p-8 text-center shadow-sm border border-gray-100">
				<div class="text-5xl mb-4">✅</div>
				<h2 class="text-2xl font-black text-gray-900 mb-2">Staff AI aktif!</h2>
				<p class="text-gray-600 mb-6">Staff AI sudah siap membantu tim Anda di WhatsApp.</p>
				<a href="/dashboard" class="block bg-primary text-white font-bold py-3 rounded-xl">Lihat Langganan</a>
			</div>
		{/if}
	</div>
</div>