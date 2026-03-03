/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#09090b',      // Deep Obsidian
          card: '#18181b',    // Surface
          primary: '#3c83f6', // Electric Blue
          accent: '#a855f7',  // Purple Accent
          border: '#27272a',
          text: '#a1a1aa'
        }
      },
      fontFamily: {
        sans: ['Space Grotesk', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      // 注入 A2S 动画曲线
      transitionTimingFunction: {
        'a2s-liquid': 'cubic-bezier(0.23, 1, 0.32, 1)',
      }
    },
  },
  plugins: [],
}
