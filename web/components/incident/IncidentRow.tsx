import Link from 'next/link';
import type { IncidentSummary, Severity } from '@/lib/types';
import { SeverityTag } from './SeverityTag';
import { formatPercent, formatDateTime } from '@/lib/format';

const BAR: Record<Severity, string> = {
  low: 'bg-sev-low',
  medium: 'bg-sev-medium',
  high: 'bg-sev-high',
  critical: 'bg-sev-high',
};

export function IncidentRow({ incident }: { incident: IncidentSummary }) {
  return (
    <Link
      href={`/incidents/${incident.id}/`}
      data-incident-link
      className="group relative grid grid-cols-[auto_1fr_auto_auto] items-center gap-4 border-b border-border py-4 pl-5 pr-4 transition-colors hover:bg-surface"
    >
      <span
        className={`absolute left-0 top-0 h-full w-0.5 origin-top scale-y-0 transition-transform duration-200 group-hover:scale-y-100 ${BAR[incident.severity]}`}
        aria-hidden
      />
      <SeverityTag severity={incident.severity} />
      <div className="min-w-0">
        <div className="truncate font-sans text-ink">{incident.title}</div>
        <div className="truncate font-mono text-xs text-ink-muted">{incident.asset}</div>
      </div>
      <div className="text-right font-mono text-sm">
        <div className="text-ink">{formatPercent(incident.confidence)}</div>
        <div className="text-xs text-ink-muted">{formatDateTime(incident.detectedAt)}</div>
      </div>
      <span
        className="font-mono text-ink-muted transition-all group-hover:translate-x-0.5 group-hover:text-accent"
        aria-hidden
      >
        →
      </span>
    </Link>
  );
}
