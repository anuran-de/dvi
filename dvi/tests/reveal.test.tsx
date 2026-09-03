import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Force reduced motion so the test asserts the accessible path.
vi.mock('framer-motion', async (orig) => {
  const actual = await orig<typeof import('framer-motion')>();
  return { ...actual, useReducedMotion: () => true };
});

import { Reveal } from '@/components/motion/Reveal';

describe('Reveal', () => {
  it('renders its children with content intact under reduced motion', () => {
    render(<Reveal><p>visible content</p></Reveal>);
    expect(screen.getByText('visible content')).toBeInTheDocument();
  });
});
