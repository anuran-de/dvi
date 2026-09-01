import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'var(--canvas)',
        surface: 'var(--surface)',
        ink: 'var(--ink)',
        'ink-muted': 'var(--ink-muted)',
        border: 'var(--border)',
        accent: 'var(--accent)',
        'sev-low': 'var(--sev-low)',
        'sev-medium': 'var(--sev-medium)',
        'sev-high': 'var(--sev-high)',
      },
      fontFamily: {
        serif: ['var(--font-serif)', 'Georgia', 'serif'],
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      borderRadius: { DEFAULT: '3px', sm: '2px', md: '4px' },
    },
  },
  plugins: [],
};
export default config;
