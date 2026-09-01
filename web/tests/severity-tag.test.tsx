import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SeverityTag } from '@/components/incident/SeverityTag';

describe('SeverityTag', () => {
  it('always shows a text label (never color alone)', () => {
    render(<SeverityTag severity="high" />);
    expect(screen.getByText(/high/i)).toBeInTheDocument();
  });
  it('exposes the severity for styling and testing', () => {
    const { container } = render(<SeverityTag severity="critical" />);
    expect(container.querySelector('[data-severity="critical"]')).not.toBeNull();
  });
});
