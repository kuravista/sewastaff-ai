export async function getStaff() {
	const res = await fetch('/api/staff');
	if (!res.ok) throw new Error('Failed to fetch staff');
	return res.json();
}

export async function getStaffBySlug(slug: string) {
	const res = await fetch(`/api/staff/${slug}`);
	if (!res.ok) throw new Error('Failed to fetch staff details');
	return res.json();
}

export async function startOnboarding(data: any) {
	const res = await fetch('/api/onboarding', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error('Failed to start onboarding');
	return res.json();
}

export async function getOnboardingStatus(rentalId: string) {
	const res = await fetch(`/api/onboarding/${rentalId}`);
	if (!res.ok) throw new Error('Failed to get onboarding status');
	return res.json();
}

export async function startTrial(slug: string) {
	const res = await fetch('/api/trial/start', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ template_slug: slug })
	});
	if (!res.ok) throw new Error('Failed to start trial');
	return res.json();
}

export async function sendTrialMessage(trialId: string, message: string) {
	const res = await fetch('/api/trial/message', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ trial_id: trialId, message })
	});
	if (!res.ok) throw new Error('Failed to send message');
	return res.json();
}

// Rental API
export async function createRental(templateSlug: string, tenantName: string, tenantPhone: string) {
	const res = await fetch('/api/rental/create', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ template_slug: templateSlug, tenant_name: tenantName, tenant_phone: tenantPhone })
	});
	if (!res.ok) throw new Error('Failed to create rental');
	return res.json();
}

export async function bindGroup(rentalId: string, inviteLink: string) {
	const res = await fetch(`/api/rental/${rentalId}/bind-group`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ invite_link: inviteLink })
	});
	if (!res.ok) throw new Error('Failed to bind group');
	return res.json();
}

export async function getBinding(rentalId: string) {
	const res = await fetch(`/api/rental/${rentalId}/binding`);
	if (!res.ok) throw new Error('Failed to get binding');
	return res.json();
}

export async function getRental(rentalId: string) {
	const res = await fetch(`/api/rental/${rentalId}`);
	if (!res.ok) throw new Error('Failed to get rental');
	return res.json();
}