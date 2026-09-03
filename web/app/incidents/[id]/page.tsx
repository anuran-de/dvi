import Link from 'next/link';
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

function SectionHeading({ index, children }: { index: string; children: React.ReactNode }) {
  return (
    <h2 className="flex items-baseline gap-3 font-serif text-xl text-ink">
      <span className="font-mono text-xs text-ink-muted">{index}</span>
      {children}
    </h2>
  );
}

export default async function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const incident = await getIncident(id);
  if (!incident) notFound();

  return (
    <main className="py-14">
      <Container className="space-y-12">
        <div>
          <Link
            href="/incidents/"
            className="link-underline font-mono text-xs uppercase tracking-wide text-ink-muted"
          >
            ← All incidents
          </Link>
        </div>

        <header className="space-y-5">
          <div className="flex items-center gap-3">
            <SeverityTag severity={incident.severity} />
            <span className="font-mono text-xs text-ink-muted">{incident.asset}</span>
          </div>
          <h1 className="max-w-3xl font-serif text-3xl leading-tight tracking-tight text-ink md:text-4xl">
            {incident.title}
          </h1>
          <p className="max-w-2xl font-sans leading-relaxed text-ink-muted">{incident.summary}</p>
          <div className="grid grid-cols-3 gap-px overflow-hidden rounded-md border border-border bg-border sm:inline-grid sm:auto-cols-max sm:grid-flow-col">
            <div className="bg-canvas px-5 py-3">
              <Stat label="Confidence" value={formatPercent(incident.confidence)} mono />
            </div>
            <div className="bg-canvas px-5 py-3">
              <Stat label="Severity" value={incident.severity} />
            </div>
            <div className="bg-canvas px-5 py-3">
              <Stat label="Downstream" value={String(incident.affectedAssets.length)} mono />
            </div>
          </div>
        </header>

        <section className="space-y-4">
          <SectionHeading index="01">Timeline</SectionHeading>
          <Card className="p-6 shadow-[var(--shadow-card)]">
            <Timeline changeAt={incident.changeAt} detectedAt={incident.detectedAt} />
          </Card>
        </section>

        <section className="space-y-4">
          <SectionHeading index="02">Blast radius</SectionHeading>
          <Card className="p-6 shadow-[var(--shadow-card)]">
            <BlastRadiusGraph
              targets={incident.rootCause.targets}
              affected={incident.affectedAssets}
              exposures={incident.businessImpact?.exposures ?? []}
            />
          </Card>
        </section>

        <section className="space-y-4">
          <SectionHeading index="03">Evidence</SectionHeading>
          <Card className="p-6 shadow-[var(--shadow-card)]">
            <EvidenceList items={incident.evidence} />
          </Card>
        </section>

        {incident.businessImpact && (
          <section className="space-y-4">
            <SectionHeading index="04">Business impact</SectionHeading>
            <Card className="p-6 shadow-[var(--shadow-card)]">
              <BusinessImpactPanel impact={incident.businessImpact} />
            </Card>
          </section>
        )}
      </Container>
    </main>
  );
}
