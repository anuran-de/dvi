import { describe, it, expect } from 'vitest';
import { getIncidents, getIncident, SEVERITY_RANK } from '@/lib/data';

describe('data seam', () => {
  it('loads incident summaries from fixtures, most severe first', async () => {
    const items = await getIncidents();
    expect(items.length).toBeGreaterThan(0);
    for (let i = 1; i < items.length; i++) {
      expect(SEVERITY_RANK[items[i - 1].severity]).toBeGreaterThanOrEqual(
        SEVERITY_RANK[items[i].severity],
      );
    }
  });
  it('loads a full incident detail by id', async () => {
    const items = await getIncidents();
    const detail = await getIncident(items[0].id);
    expect(detail).not.toBeNull();
    expect(detail!.id).toBe(items[0].id);
    expect(Array.isArray(detail!.evidence)).toBe(true);
  });
  it('returns null for an unknown id', async () => {
    expect(await getIncident('does-not-exist')).toBeNull();
  });
});
