<script lang="ts">
	import { page } from '$app/stores';
	import { startTrial, sendTrialMessage } from '$lib/api';
	import { onMount } from 'svelte';
	import ChatBubble from '$lib/components/ChatBubble.svelte';

	const staffId = $page.params.id;
	const MAX_MESSAGES = 8;

	let trialId = '';
	let staffName = 'Staff AI';
	let staffEmoji = '🤖';
	let messages: { message: string; isUser: boolean }[] = [];
	let inputText = '';
	let remaining = MAX_MESSAGES;
	let isTyping = false;
	let limitReached = false;
	let loading = true;

	onMount(async () => {
		try {
			const trial = await startTrial(staffId);
			trialId = trial.trial_id;
			staffName = trial.staff_name || 'Staff AI';
			staffEmoji = trial.avatar_emoji || '🤖';
			messages = [{ message: `Halo! Saya ${staffName}. Ada yang bisa saya bantu?`, isUser: false }];
		} catch {
			messages = [{ message: 'Halo! Ada yang bisa saya bantu?', isUser: false }];
			trialId = 'demo';
		}
		loading = false;
	});

	async function sendMessage() {
		if (!inputText.trim() || limitReached) return;
		const text = inputText;
		inputText = '';
		messages = [...messages, { message: text, isUser: true }];
		remaining -= 1;

		if (remaining <= 0) {
			limitReached = true;
			return;
		}

		isTyping = true;
		try {
			let reply;
			if (trialId === 'demo') {
				await new Promise(r => setTimeout(r, 1000));
				reply = { reply: 'Terima kasih! Untuk demo ini, coba sewa versi penuhnya ya 😊' };
			} else {
				reply = await sendTrialMessage(trialId, text);
			}
			messages = [...messages, { message: reply.reply, isUser: false }];
		} catch {
			messages = [...messages, { message: 'Maaf, terjadi error. Coba lagi ya.', isUser: false }];
		}
		isTyping = false;
	}
</script>

<div class="min-h-screen flex flex-col bg-gray-50">
	<!-- Header -->
	<nav class="sticky top-0 z-40 bg-white border-b border-gray-100 px-4 py-3 flex items-center gap-3">
		<a href="/" class="text-gray-600"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg></a>
		<div class="w-8 h-8 bg-primary-light rounded-full flex items-center justify-center text-lg">{staffEmoji}</div>
		<div class="flex-1">
			<p class="font-bold text-gray-900 text-sm">{staffName}</p>
			<p class="text-xs text-green-500">Online</p>
		</div>
		<div class="flex items-center gap-1 bg-primary-light px-3 py-1 rounded-full">
			<span class="text-xs font-bold text-primary">{remaining}</span>
			<span class="text-xs text-primary">pesan tersisa</span>
		</div>
	</nav>

	<!-- Chat -->
	<div class="flex-1 overflow-y-auto p-4 space-y-1 pb-24">
		{#if loading}
			<div class="flex justify-center py-10"><div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></div></div>
		{/if}
		{#each messages as m}
			<ChatBubble message={m.message} isUser={m.isUser} avatarEmoji={staffEmoji} />
		{/each}
		{#if isTyping}
			<div class="flex items-center gap-2 mb-4">
				<div class="w-8 h-8 rounded-full bg-primary-light flex-shrink-0 flex items-center justify-center text-sm">{staffEmoji}</div>
				<div class="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
					<div class="flex gap-1">
						<div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:0ms"></div>
						<div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:150ms"></div>
						<div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:300ms"></div>
					</div>
				</div>
			</div>
		{/if}
	</div>

	<!-- Input -->
	{#if !limitReached}
		<div class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-3 flex gap-3">
			<input type="text" bind:value={inputText} on:keydown={(e) => e.key === 'Enter' && sendMessage()} placeholder="Tulis pesan..." class="flex-1 border border-gray-200 rounded-full px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
			<button on:click={sendMessage} class="w-10 h-10 bg-primary rounded-full flex items-center justify-center flex-shrink-0 hover:bg-primary-dark transition-colors">
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
			</button>
		</div>
	{/if}

	<!-- Limit overlay -->
	{#if limitReached}
		<div class="fixed inset-0 bg-black/60 z-50 flex items-end">
			<div class="w-full bg-white rounded-t-3xl p-8 text-center">
				<div class="text-4xl mb-3">⏰</div>
				<h3 class="text-xl font-bold text-gray-900 mb-2">Trial Habis!</h3>
				<p class="text-gray-600 mb-6">Sewa {staffName} untuk chat tanpa batas & gunakan di grup WhatsApp Anda.</p>
				<a href="/sewa/{staffId}" class="block w-full py-4 bg-primary text-white font-bold rounded-xl mb-3">Sewa Sekarang</a>
				<a href="/" class="block text-gray-500 text-sm">Kembali ke Beranda</a>
			</div>
		</div>
	{/if}
</div>