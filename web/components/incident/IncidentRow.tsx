import Link from 'next/link';
import type { IncidentSummary } from '@/lib/types';
import { SeverityTag } from './SeverityTag';
import { formatPercent, formatDateTime } from '@/lib/format';

export function IncidentRow({ incident }: { incident: IncidentSummary }) {
  return (
    <Link
      href={`/incidents/${incident.id}/`}
      className="group grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-border px-4 py-4 transition-colors hover:bg-surface"
    >
      <SeverityTag severity={incident.severity} />
      <div className="min-w-0">
        <div className="truncate font-sans text-ink">{incident.title}</div>
        <div className="truncate font-mono text-xs text-ink-muted">{incident.asset}</div>
      </div>
      <div className="text-right font-mono text-sm text-ink-muted">
        <div className="text-ink">{formatPercent(incident.confidence)}</div>
        <div className="text-xs">{formatDateTime(incident.detectedAt)}</div>
      </div>
    </Link>
  );
}
