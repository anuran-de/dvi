import type { IncidentDetail } from '@/lib/types';

type Impact = IncidentDetail['businessImpact'];

export function BusinessImpactPanel({ impact }: { impact: Impact }) {
  if (impact === null) return null;
  return (
    <table className="w-full border-collapse font-mono text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-ink-muted">
          <th className="py-2 font-normal">Exposure</th>
          <th className="py-2 font-normal">Type</th>
          <th className="py-2 font-normal">Criticality</th>
          <th className="py-2 font-normal">Owner</th>
        </tr>
      </thead>
      <tbody>
        {impact.exposures.map((e) => (
          <tr key={e.name} className="border-b border-border">
            <td className="py-2 text-ink">{e.name}</td>
            <td className="py-2 text-ink-muted">{e.type}</td>
            <td className="py-2 text-ink">{e.criticality}</td>
            <td className="py-2 text-ink-muted">{e.owner ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
