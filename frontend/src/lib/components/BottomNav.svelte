<script lang="ts">
	import { page } from '$app/stores';

	const tabs = [
		{ name: 'Beranda', path: '/', icon: '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline>' },
		{ name: 'Staff AI', path: '/staff', icon: '<circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line>' },
		{ name: 'Grup Saya', path: '/groups', icon: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>' },
		{ name: 'Langganan', path: '/dashboard', icon: '<rect x="2" y="5" width="20" height="14" rx="2"></rect><line x1="2" y1="10" x2="22" y2="10"></line>' },
		{ name: 'Akun', path: '/account', icon: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>' }
	];

	$: isActive = (path: string) => {
		if (path === '/' && $page.url.pathname !== '/') return false;
		return $page.url.pathname.startsWith(path);
	};
</script>

<div class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 pb-safe z-50">
	<div class="flex justify-around items-center h-16">
		{#each tabs as tab}
			<a href={tab.path} class="flex flex-col items-center justify-center w-full h-full gap-1 {isActive(tab.path) ? 'text-primary' : 'text-gray-400 hover:text-gray-600'}">
				<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					{@html tab.icon}
				</svg>
				<span class="text-[10px] font-medium">{tab.name}</span>
			</a>
		{/each}
	</div>
</div>