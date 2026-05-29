import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': 'http://app:8000',
			'/webhooks': 'http://app:8000'
		}
	}
});
