import Link from 'next/link';
import type { IncidentDetail } from '@/lib/types';
import { SeverityTag } from '@/components/incident/SeverityTag';
import { formatPercent, formatDateTime } from '@/lib/format';

/**
 * A real, engine-produced incident rendered as a specimen card on the
 * landing page. All fields come straight through the data seam
 * (`lib/data.ts`) from `web/content/incidents/*.json` — nothing here is
 * hand-authored.
 */
export function IncidentSpecimen({ incident }: { incident: IncidentDetail }) {
  return (
    <div className="rounded-md border border-border bg-canvas-raised shadow-card">
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <SeverityTag severity={incident.severity} />
          <span className="font-mono text-xs text-ink-muted">{incident.asset}</span>
        </div>
        <span className="font-mono text-xs text-ink-muted">{formatDateTime(incident.detectedAt)}</span>
      </div>
      <div className="space-y-3 px-5 py-4">
        <p className="font-serif text-lg leading-snug text-ink">{incident.title}</p>
        <p className="font-mono text-xs leading-relaxed text-ink-muted">
          <span className="select-none text-accent">›</span> {incident.evidence[0]}
        </p>
        <div className="flex items-center justify-between pt-1">
          <span className="font-mono text-xs uppercase tracking-wide text-ink-muted">
            Confidence <span className="text-ink">{formatPercent(incident.confidence)}</span>
          </span>
          <Link
            href={`/incidents/${incident.id}/`}
            className="font-mono text-xs text-accent underline-offset-4 hover:underline"
          >
            View full incident →
          </Link>
        </div>
      </div>
    </div>
  );
}
