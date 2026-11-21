import frappeUIPreset from 'frappe-ui/tailwind'

/** @type {import('tailwindcss').Config} */
export default {
  presets: [frappeUIPreset],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    // Root components (Button, Dialog, FormControl, …)
    './node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
    // Charts (BarChart / DonutChart tokens + layout utilities)
    './node_modules/frappe-ui/src/charts/**/*.{vue,js,ts,jsx,tsx}',
    // Experimental Calendar (Month/Week/Day grids use grid-cols-7, etc.)
    './node_modules/frappe-ui/experimental/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
