import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Hero } from '@/components/landing/Hero';
import { HowItWorks } from '@/components/landing/HowItWorks';

// next/link's href normalization reads next.config's `trailingSlash` setting
// from `process.env.__NEXT_TRAILING_SLASH`, which is only injected by the real
// Next.js build. This repo's next.config.mjs sets `trailingSlash: true`
// (required for the static export's `/incidents/` route), so mirror that here
// for jsdom-rendered <Link> assertions.
process.env.__NEXT_TRAILING_SLASH = 'true';

describe('landing', () => {
  it('hero states the core problem and links to incidents', () => {
    render(<Hero />);
    expect(screen.getByText(/silent/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /incident/i })).toHaveAttribute('href', '/incidents/');
  });
  it('how-it-works lists the four pipeline stages', () => {
    render(<HowItWorks />);
    for (const stage of ['Profile', 'Detect', 'Rank', 'Blast radius']) {
      expect(screen.getByText(stage)).toBeInTheDocument();
    }
  });
});
