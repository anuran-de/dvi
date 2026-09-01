import { getIncidents } from '@/lib/data';
import { IncidentList } from '@/components/incident/IncidentList';
import { Container } from '@/components/ui/Container';

export default async function IncidentsPage() {
  const items = await getIncidents();
  return (
    <main className="py-16">
      <Container>
        <h1 className="mb-2 font-serif text-3xl text-ink">Incidents</h1>
        <p className="mb-8 font-sans text-ink-muted">
          Semantic data changes detected across your assets.
        </p>
        <IncidentList items={items} />
      </Container>
    </main>
  );
}
