import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#040506',
          card: '#0a0c10',
          raised: '#12121a',
          border: '#141c28',
        },
        accent: {
          cyan: '#00d4ff',
          cyanGlow: 'rgba(0,212,255,0.35)',
        },
        status: {
          green: '#00ff88',
          amber: '#f0a500',
          red: '#ff4444',
        },
        text: {
          primary: '#e4ecf7',
          secondary: '#5a7090',
          muted: '#2e3d50',
        },
      },
      fontFamily: {
        display: ['var(--font-space-grotesk)', 'system-ui', 'sans-serif'],
        body: ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'monospace'],
      },
      animation: {
        'fade-up': 'fadeUp 0.6s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
        'pulse-red': 'pulseRed 2.5s ease-in-out infinite',
        'glow-cyan': 'glowCyan 2s ease-in-out infinite',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseRed: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(255, 68, 68, 0)' },
          '50%': { boxShadow: '0 0 18px 2px rgba(255, 68, 68, 0.3)' },
        },
        glowCyan: {
          '0%, 100%': { boxShadow: '0 0 8px 0 rgba(0, 212, 255, 0.15)' },
          '50%': { boxShadow: '0 0 18px 2px rgba(0, 212, 255, 0.35)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};

export default config;
