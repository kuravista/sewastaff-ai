<script lang="ts">
	const fallbackRentals = [
		{ staffName: 'Rara - CS Pro', emoji: '👩🏻‍💼', specialty: 'Customer Service', status: 'Aktif', groupName: 'Tim CS *********', expiry: '2025-08-01', price: 299000 },
		{ staffName: 'Budi - HR Admin', emoji: '👨🏻‍💼', specialty: 'Human Resources', status: 'Trial', groupName: 'HR Team *****', expiry: '2025-06-15', price: 0 },
		{ staffName: 'Sinta - Sales AI', emoji: '👩🏻‍🎤', specialty: 'Sales & Marketing', status: 'Expired', groupName: 'Marketing ****', expiry: '2025-04-01', price: 349000 }
	];

	const statusColor: Record<string, string> = {
		Aktif: 'bg-green-50 text-green-700',
		Trial: 'bg-yellow-50 text-yellow-700',
		Expired: 'bg-red-50 text-red-500'
	};

	const formatPrice = (price: number) => new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(price);
</script>

<div class="min-h-screen bg-gray-50 px-4 py-6 pb-24">
	<div class="max-w-xl mx-auto">
		<a href="/" class="text-sm text-primary font-semibold">← Beranda</a>
		<h1 class="text-2xl font-black text-gray-900 mt-4 mb-2">Langganan</h1>
		<p class="text-gray-600 mb-6">Daftar staff AI yang sedang Anda sewa.</p>

		<div class="space-y-4">
			{#each fallbackRentals as rental}
				<div class="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
					<div class="flex items-center justify-between mb-3">
						<div class="flex items-center gap-3">
							<div class="w-10 h-10 bg-primary-light rounded-full flex items-center justify-center text-xl">{rental.emoji}</div>
							<div>
								<h3 class="font-bold text-gray-900 text-sm">{rental.staffName}</h3>
								<p class="text-xs text-gray-500">{rental.specialty}</p>
							</div>
						</div>
						<span class="text-xs font-bold px-3 py-1 rounded-full {statusColor[rental.status]}">{rental.status}</span>
					</div>
					<div class="grid grid-cols-2 gap-y-2 text-sm text-gray-600">
						<p>Grup:</p>
						<p class="text-right font-medium text-gray-800">{rental.groupName}</p>
						<p>Expired:</p>
						<p class="text-right font-medium text-gray-800">{rental.expiry}</p>
						{#if rental.price > 0}
							<p>Harga:</p>
							<p class="text-right font-bold text-gray-900">{formatPrice(rental.price)}/bln</p>
						{/if}
					</div>
					{#if rental.status === 'Expired'}
						<button class="w-full mt-4 bg-primary text-white font-bold py-2.5 rounded-xl text-sm">Perpanjang</button>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>