export type Severity = 'low' | 'medium' | 'high' | 'critical';

export interface IncidentSummary {
  id: string;
  asset: string;
  severity: Severity;
  title: string;
  confidence: number | null;
  detectedAt: string;
  changeAt: string;
}

export interface Exposure {
  name: string;
  type: string;
  criticality: string;
  owner: string | null;
}

export interface IncidentDetail extends IncidentSummary {
  summary: string;
  evidence: string[];
  affectedAssets: string[];
  rootCause: { label: string; targets: string[]; timestamp: string };
  businessImpact: { exposures: Exposure[]; maxCriticality: string | null } | null;
}
