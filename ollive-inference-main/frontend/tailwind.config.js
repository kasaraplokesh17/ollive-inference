/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        sans: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        ollive: {
          bg: '#0a0a0f',
          surface: '#111118',
          border: '#1e1e2e',
          accent: '#7c6af7',
          'accent-hover': '#9d8ff9',
          muted: '#6b7280',
          text: '#e2e8f0',
          'text-dim': '#94a3b8',
        }
      }
    }
  },
  plugins: []
}
