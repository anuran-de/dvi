import type { IncidentDetail, IncidentSummary, Severity } from './types';
import index from '@/content/incidents/index.json';

export const SEVERITY_RANK: Record<Severity, number> = {
  critical: 3, high: 2, medium: 1, low: 0,
};

// The seam: today these read bundled JSON. Swapping to a live API means
// replacing the two loader bodies below — no component changes.
export async function getIncidents(): Promise<IncidentSummary[]> {
  const items = index as IncidentSummary[];
  return [...items].sort(
    (a, b) =>
      SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] ||
      b.detectedAt.localeCompare(a.detectedAt),
  );
}

export async function getIncident(id: string): Promise<IncidentDetail | null> {
  try {
    const mod = await import(`@/content/incidents/${id}.json`);
    return mod.default as IncidentDetail;
  } catch {
    return null;
  }
}
