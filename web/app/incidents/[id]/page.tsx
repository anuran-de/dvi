import { notFound } from 'next/navigation';
import { getIncident, getIncidents } from '@/lib/data';
import { Container } from '@/components/ui/Container';
import { Card } from '@/components/ui/Card';
import { Stat } from '@/components/ui/Stat';
import { SeverityTag } from '@/components/incident/SeverityTag';
import { Timeline } from '@/components/incident/Timeline';
import { EvidenceList } from '@/components/incident/EvidenceList';
import { BusinessImpactPanel } from '@/components/incident/BusinessImpactPanel';
import { BlastRadiusGraph } from '@/components/incident/BlastRadiusGraph';
import { formatPercent } from '@/lib/format';

export async function generateStaticParams() {
  const items = await getIncidents();
  return items.map((i) => ({ id: i.id }));
}

export default async function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const incident = await getIncident(id);
  if (!incident) notFound();

  return (
    <main className="py-16">
      <Container className="space-y-10">
        <header className="space-y-4 border-b border-border pb-8">
          <div className="flex items-center gap-3">
            <SeverityTag severity={incident.severity} />
            <span className="font-mono text-xs text-ink-muted">{incident.asset}</span>
          </div>
          <h1 className="max-w-3xl font-serif text-3xl leading-tight text-ink md:text-4xl">
            {incident.title}
          </h1>
          <p className="max-w-2xl font-sans text-ink-muted">{incident.summary}</p>
          <div className="flex flex-wrap gap-10 pt-2">
            <Stat label="Confidence" value={formatPercent(incident.confidence)} mono />
            <Stat label="Severity" value={incident.severity} />
            <Stat label="Downstream" value={String(incident.affectedAssets.length)} mono />
          </div>
        </header>

        <Card raised className="p-6">
          <Timeline changeAt={incident.changeAt} detectedAt={incident.detectedAt} />
        </Card>

        <section className="space-y-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-ink-muted">Lineage</p>
            <h2 className="font-serif text-xl text-ink">Blast radius</h2>
          </div>
          <Card raised className="overflow-x-auto p-6">
            <BlastRadiusGraph
              targets={incident.rootCause.targets}
              affected={incident.affectedAssets}
              exposures={incident.businessImpact?.exposures ?? []}
            />
          </Card>
        </section>

        <section className="space-y-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-ink-muted">Root cause</p>
            <h2 className="font-serif text-xl text-ink">Evidence</h2>
          </div>
          <Card raised className="p-6">
            <EvidenceList items={incident.evidence} />
          </Card>
        </section>

        {incident.businessImpact && (
          <section className="space-y-4">
            <div>
              <p className="font-mono text-xs uppercase tracking-widest text-ink-muted">Exposures</p>
              <h2 className="font-serif text-xl text-ink">Business impact</h2>
            </div>
            <Card raised className="p-6">
              <BusinessImpactPanel impact={incident.businessImpact} />
            </Card>
          </section>
        )}
      </Container>
    </main>
  );
}
