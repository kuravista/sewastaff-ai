<script lang="ts">
	export let slug: string;
	export let name: string;
	export let specialty: string;
	export let avatarEmoji: string;
	export let features: string[];
	export let priceMonthlyIdr: number;
	export let isCustom: boolean = false;

	const formatPrice = (price: number) => {
		return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 }).format(price);
	};
</script>

<div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col h-full hover:shadow-md transition-shadow relative overflow-hidden">
	{#if isCustom}
		<div class="absolute top-0 right-0 bg-primary text-white text-xs font-bold px-3 py-1 rounded-bl-lg">CUSTOM</div>
	{/if}
	<div class="flex items-center gap-3 mb-4">
		<div class="w-12 h-12 bg-primary-light rounded-full flex items-center justify-center text-2xl">
			{avatarEmoji}
		</div>
		<div>
			<h3 class="font-bold text-gray-900 leading-tight">{name}</h3>
			<p class="text-xs text-primary font-medium">{specialty}</p>
		</div>
	</div>

	<ul class="space-y-2 mb-6 flex-grow">
		{#each features as feature}
			<li class="text-sm text-gray-600 flex items-start gap-2">
				<span class="text-primary mt-0.5">✓</span>
				<span>{feature}</span>
			</li>
		{/each}
	</ul>

	<div class="mt-auto border-t border-gray-100 pt-4">
		<div class="mb-3">
			<span class="text-lg font-bold text-gray-900">{formatPrice(priceMonthlyIdr)}</span>
			<span class="text-xs text-gray-500">/bln</span>
		</div>
		<div class="grid grid-cols-2 gap-2">
			<a href="/try/{slug}" class="text-center py-2 px-3 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">Coba</a>
			<a href="/staff/{slug}" class="text-center py-2 px-3 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors">Sewa</a>
		</div>
	</div>
</div>