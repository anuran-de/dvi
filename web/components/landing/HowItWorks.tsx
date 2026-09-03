'use client';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

const STAGES = [
  {
    name: 'Profile',
    body: 'Snapshot each column before and after a change — distributions, not just schemas.',
  },
  {
    name: 'Detect',
    body: 'Signature detectors flag semantic shifts a structural check can never see.',
  },
  {
    name: 'Rank',
    body: 'Corroborate symptoms against the lineage and rank the most likely root cause.',
  },
  {
    name: 'Blast radius',
    body: 'Project the change onto downstream assets and the external consumers at risk.',
  },
];

export function HowItWorks() {
  return (
    <section className="py-24">
      <Container>
        <Reveal>
          <h2 className="font-serif text-3xl text-ink">How it works</h2>
          <p className="mt-3 max-w-lg font-sans text-ink-muted">
            One deterministic pipeline, from raw column to a ranked, evidenced incident.
          </p>
        </Reveal>
        <div className="relative mt-14 grid gap-10 md:grid-cols-4">
          <div
            aria-hidden="true"
            className="absolute left-0 right-0 top-[1.375rem] hidden h-px bg-border md:block"
          />
          {STAGES.map((s, i) => (
            <Reveal key={s.name} delay={i * 0.06}>
              <div className="group relative pt-4">
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full border border-border bg-canvas font-mono text-sm text-ink-muted transition-colors group-hover:border-accent group-hover:text-accent">
                  0{i + 1}
                </div>
                <h3 className="font-serif text-xl text-ink">{s.name}</h3>
                <p className="mt-2 font-sans text-sm leading-relaxed text-ink-muted">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
