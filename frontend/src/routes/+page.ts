import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const res = await fetch('/api/staff');
		if (!res.ok) return { staff: fallbackStaff };
		const staff = await res.json();
		return { staff };
	} catch {
		return { staff: fallbackStaff };
	}
};

const fallbackStaff = [
	{
		slug: 'staff-cs',
		name: 'Rara - CS Pro',
		specialty: 'Customer Service',
		avatarEmoji: '👩🏻‍💼',
		features: ['Balas komplain otomatis', 'Follow-up pelanggan', 'Template respon profesional'],
		priceMonthlyIdr: 299000,
		isCustom: false
	},
	{
		slug: 'staff-hr',
		name: 'Budi - HR Admin',
		specialty: 'Human Resources',
		avatarEmoji: '👨🏻‍💼',
		features: ['Absensi otomatis', 'Info gaji & tunjangan', 'Rekap kehadiran'],
		priceMonthlyIdr: 399000,
		isCustom: false
	},
	{
		slug: 'staff-sales',
		name: 'Sinta - Sales AI',
		specialty: 'Sales & Marketing',
		avatarEmoji: '👩🏻‍🎤',
		features: ['Follow-up leads', 'Kirim promo otomatis', 'Laporan penjualan harian'],
		priceMonthlyIdr: 349000,
		isCustom: false
	},
	{
		slug: 'staff-pa',
		name: 'Andi - PA Digital',
		specialty: 'Personal Assistant',
		avatarEmoji: '🧑🏻‍💻',
		features: ['Atur jadwal & reminder', 'Notulen rapat', 'Draft email & laporan'],
		priceMonthlyIdr: 449000,
		isCustom: false
	}
];
