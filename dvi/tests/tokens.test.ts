import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

describe('design tokens', () => {
  const css = readFileSync(resolve(__dirname, '../styles/tokens.css'), 'utf8');
  it('defines the editorial canvas and single accent', () => {
    expect(css).toContain('--canvas: #FAFAF7');
    expect(css).toContain('--accent: #1F3A5F');
  });
  it('defines the three muted severity colors', () => {
    expect(css).toContain('--sev-low: #3F7A5E');
    expect(css).toContain('--sev-medium: #B07A2E');
    expect(css).toContain('--sev-high: #A23B34');
  });
  it('defines the motion duration scale', () => {
    expect(css).toContain('--motion-fast: 160ms');
    expect(css).toContain('--motion-base: 240ms');
    expect(css).toContain('--motion-slow: 420ms');
  });
});
