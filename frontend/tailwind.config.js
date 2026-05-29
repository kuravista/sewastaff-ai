/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			colors: {
				primary: { DEFAULT: '#7C3AED', light: '#EDE9FE', dark: '#5B21B6' }
			},
			fontFamily: {
				sans: ['Inter', 'sans-serif']
			}
		}
	},
	plugins: []
};
