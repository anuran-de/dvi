'use client';
import { useState } from 'react';
import type { IncidentSummary, Severity } from '@/lib/types';
import { SEVERITY_RANK } from '@/lib/data';
import { IncidentRow } from './IncidentRow';

type SortKey = 'severity' | 'confidence' | 'recent';
const SEVERITIES: (Severity | 'all')[] = ['all', 'critical', 'high', 'medium', 'low'];

export function filterAndSort(
  items: IncidentSummary[],
  severity: Severity | 'all',
  sort: SortKey,
): IncidentSummary[] {
  const filtered = severity === 'all' ? items : items.filter((i) => i.severity === severity);
  const byId = (a: IncidentSummary, b: IncidentSummary) => a.id.localeCompare(b.id);
  const cmp: Record<SortKey, (a: IncidentSummary, b: IncidentSummary) => number> = {
    severity: (a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] || byId(a, b),
    confidence: (a, b) => (b.confidence ?? -1) - (a.confidence ?? -1) || byId(a, b),
    recent: (a, b) => b.detectedAt.localeCompare(a.detectedAt) || byId(a, b),
  };
  return [...filtered].sort(cmp[sort]);
}

export function IncidentList({ items }: { items: IncidentSummary[] }) {
  const [severity, setSeverity] = useState<Severity | 'all'>('all');
  const [sort, setSort] = useState<SortKey>('severity');
  const rows = filterAndSort(items, severity, sort);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-2 font-mono text-xs">
        {SEVERITIES.map((s) => (
          <button
            key={s}
            onClick={() => setSeverity(s)}
            aria-pressed={severity === s}
            className={`rounded-sm border px-2 py-1 uppercase tracking-wide transition-colors ${
              severity === s ? 'border-accent text-accent' : 'border-border text-ink-muted hover:text-ink'
            }`}
          >
            {s}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-2">
          <span className="text-ink-muted">sort</span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            aria-label="sort"
            className="rounded-sm border border-border bg-canvas px-2 py-1"
          >
            <option value="severity">severity</option>
            <option value="confidence">confidence</option>
            <option value="recent">most recent</option>
          </select>
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="font-mono text-sm text-sev-low">All clear — no incidents match this filter.</p>
      ) : (
        <div className="border-t border-border">
          {rows.map((i) => (
            <IncidentRow key={i.id} incident={i} />
          ))}
        </div>
      )}
    </div>
  );
}
