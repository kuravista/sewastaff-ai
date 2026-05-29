<script lang="ts">
	export let message: string;
	export let isUser: boolean;
	export let avatarEmoji: string = '🤖';
</script>

<div class="flex w-full {isUser ? 'justify-end' : 'justify-start'} mb-4">
	{#if !isUser}
		<div class="w-8 h-8 rounded-full bg-primary-light flex-shrink-0 flex items-center justify-center mr-2 text-sm">
			{avatarEmoji}
		</div>
	{/if}
	<div class="max-w-[80%] rounded-2xl px-4 py-2 {isUser ? 'bg-primary text-white rounded-br-sm' : 'bg-white border border-gray-100 text-gray-800 rounded-bl-sm shadow-sm'}">
		<p class="text-sm whitespace-pre-wrap">{message}</p>
	</div>
</div>