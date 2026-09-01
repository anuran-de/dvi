export interface BlastRadiusExposure {
  name: string;
  type: string;
  criticality: string;
  owner: string | null;
}

export interface BlastRadiusGraphProps {
  targets: string[];
  affected: string[];
  exposures: BlastRadiusExposure[];
}

// Minimal stub for Task 7 — Task 8 replaces this with the real graph.
export function BlastRadiusGraph(_props: BlastRadiusGraphProps) {
  return null;
}
