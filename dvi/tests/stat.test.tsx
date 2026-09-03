import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Stat } from '@/components/ui/Stat';

describe('Stat', () => {
  it('renders a label and value', () => {
    render(<Stat label="Confidence" value="87%" />);
    expect(screen.getByText('Confidence')).toBeInTheDocument();
    expect(screen.getByText('87%')).toBeInTheDocument();
  });
});
