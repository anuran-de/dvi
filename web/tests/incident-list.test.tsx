import { describe, it, expect } from 'vitest';
import { filterAndSort } from '@/components/incident/IncidentList';
import type { IncidentSummary } from '@/lib/types';

const rows: IncidentSummary[] = [
  { id: 'b', asset: 'a2', severity: 'low', title: 't', confidence: 0.5, detectedAt: '2026-08-25T09:16:00', changeAt: '2026-08-25T09:14:00' },
  { id: 'a', asset: 'a1', severity: 'high', title: 't', confidence: 0.9, detectedAt: '2026-08-24T09:16:00', changeAt: '2026-08-24T09:14:00' },
  { id: 'c', asset: 'a3', severity: 'high', title: 't', confidence: 0.7, detectedAt: '2026-08-26T09:16:00', changeAt: '2026-08-26T09:14:00' },
];

describe('filterAndSort', () => {
  it('sorts by severity desc with a stable id tie-break', () => {
    const out = filterAndSort(rows, 'all', 'severity').map((r) => r.id);
    expect(out).toEqual(['a', 'c', 'b']);
  });
  it('filters to a single severity', () => {
    expect(filterAndSort(rows, 'high', 'severity').map((r) => r.id)).toEqual(['a', 'c']);
  });
  it('sorts by confidence desc', () => {
    expect(filterAndSort(rows, 'all', 'confidence').map((r) => r.id)).toEqual(['a', 'c', 'b']);
  });
  it('sorts by most recent detection', () => {
    expect(filterAndSort(rows, 'all', 'recent').map((r) => r.id)).toEqual(['c', 'b', 'a']);
  });
});
