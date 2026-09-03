import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'var(--canvas)',
        'canvas-raised': 'var(--canvas-raised)',
        surface: 'var(--surface)',
        ink: 'var(--ink)',
        'ink-muted': 'var(--ink-muted)',
        border: 'var(--border)',
        accent: 'var(--accent)',
        'accent-soft': 'var(--accent-soft)',
        'accent-line': 'var(--accent-line)',
        'sev-low': 'var(--sev-low)',
        'sev-low-soft': 'var(--sev-low-soft)',
        'sev-medium': 'var(--sev-medium)',
        'sev-medium-soft': 'var(--sev-medium-soft)',
        'sev-high': 'var(--sev-high)',
        'sev-high-soft': 'var(--sev-high-soft)',
      },
      fontFamily: {
        serif: ['var(--font-serif)', 'Georgia', 'serif'],
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      borderRadius: { DEFAULT: '3px', sm: '2px', md: '4px', lg: '6px' },
      boxShadow: {
        edge: '0 1px 0 0 var(--border)',
        card: '0 1px 2px rgba(26, 26, 24, 0.04), 0 8px 24px -12px rgba(26, 26, 24, 0.12)',
      },
      backgroundImage: {
        grid: 'linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
};
export default config;
