/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          500: '#1d6ef5',
          600: '#1558d6',
          700: '#1045b0',
          900: '#0a2d73',
        },
        surface: {
          50: '#f8f9fc',
          100: '#f1f3f9',
          200: '#e4e8f2',
        },
      },
    },
  },
  plugins: [],
}
