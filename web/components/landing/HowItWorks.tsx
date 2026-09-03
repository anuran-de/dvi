'use client';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

const STAGES = [
  { name: 'Profile', body: 'Snapshot each column before and after a change — distributions, not just schemas.' },
  { name: 'Detect', body: 'Signature detectors flag semantic shifts a structural check can never see.' },
  { name: 'Rank', body: 'Corroborate symptoms against the lineage and rank the most likely root cause.' },
  { name: 'Blast radius', body: 'Project the change onto downstream assets and the external consumers at risk.' },
];

export function HowItWorks() {
  return (
    <section className="py-24">
      <Container>
        <Reveal>
          <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-muted">The pipeline</p>
          <h2 className="mb-12 font-serif text-3xl tracking-tight text-ink">How it works</h2>
        </Reveal>
        <div className="grid gap-px overflow-hidden rounded-md border border-border bg-border md:grid-cols-4">
          {STAGES.map((s, i) => (
            <Reveal key={s.name} delay={i * 0.06}>
              <div className="group h-full bg-canvas p-6 transition-colors hover:bg-accent-wash">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-accent">0{i + 1}</span>
                  <span className="h-1.5 w-1.5 rounded-full bg-border transition-colors group-hover:bg-accent" aria-hidden />
                </div>
                <h3 className="mt-3 font-serif text-xl text-ink">{s.name}</h3>
                <p className="mt-2 font-sans text-sm leading-relaxed text-ink-muted">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
