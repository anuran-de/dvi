import { getIncidents } from '@/lib/data';
import { IncidentList } from '@/components/incident/IncidentList';
import { Container } from '@/components/ui/Container';

export default async function IncidentsPage() {
  const items = await getIncidents();
  const critical = items.filter((i) => i.severity === 'critical' || i.severity === 'high').length;

  return (
    <main className="py-16">
      <Container>
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-border pb-8">
          <div>
            <h1 className="font-serif text-3xl text-ink">Incidents</h1>
            <p className="mt-2 font-sans text-ink-muted">
              Semantic data changes detected across your assets.
            </p>
          </div>
          <div className="font-mono text-xs uppercase tracking-widest text-ink-muted">
            {items.length} detected · <span className="text-sev-high">{critical} high or above</span>
          </div>
        </div>
        <IncidentList items={items} />
      </Container>
    </main>
  );
}
