import { describe, it, expect } from 'vitest';
import { formatPercent, formatDuration } from '@/lib/format';

describe('format helpers', () => {
  it('formats confidence as a whole percent, dash for null', () => {
    expect(formatPercent(0.87)).toBe('87%');
    expect(formatPercent(null)).toBe('—');
  });
  it('formats a lead time between change and detection', () => {
    expect(formatDuration('2026-08-25T09:14:00', '2026-08-25T09:16:00')).toBe('2m');
  });
});
