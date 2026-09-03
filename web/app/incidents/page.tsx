import { getIncidents } from '@/lib/data';
import type { Severity } from '@/lib/types';
import { IncidentList } from '@/components/incident/IncidentList';
import { Container } from '@/components/ui/Container';

const TIERS: { key: Severity; label: string; dot: string }[] = [
  { key: 'critical', label: 'Critical', dot: 'bg-sev-high' },
  { key: 'high', label: 'High', dot: 'bg-sev-high' },
  { key: 'medium', label: 'Medium', dot: 'bg-sev-medium' },
  { key: 'low', label: 'Low', dot: 'bg-sev-low' },
];

export default async function IncidentsPage() {
  const items = await getIncidents();
  const counts = items.reduce<Record<string, number>>((acc, i) => {
    acc[i.severity] = (acc[i.severity] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <main className="py-16">
      <Container>
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-muted">Operator</p>
        <h1 className="font-serif text-4xl tracking-tight text-ink">Incidents</h1>
        <p className="mt-2 max-w-xl font-sans text-ink-muted">
          Semantic data changes detected across your assets.
        </p>

        <div className="mt-8 flex flex-wrap items-stretch overflow-hidden rounded-md border border-border">
          <div className="flex flex-col justify-center bg-canvas px-5 py-3">
            <span className="font-mono text-2xl tabular-nums text-ink">{items.length}</span>
            <span className="font-mono text-[11px] uppercase tracking-wide text-ink-muted">detected</span>
          </div>
          {TIERS.map((t) => (
            <div key={t.key} className="flex flex-col justify-center border-l border-border bg-canvas px-5 py-3">
              <span className="inline-flex items-center gap-2 font-mono text-2xl tabular-nums text-ink">
                <span className={`h-2 w-2 rounded-full ${t.dot}`} aria-hidden />
                {counts[t.key] ?? 0}
              </span>
              <span className="font-mono text-[11px] uppercase tracking-wide text-ink-muted">{t.label}</span>
            </div>
          ))}
        </div>

        <div className="mt-10">
          <IncidentList items={items} />
        </div>
      </Container>
    </main>
  );
}
