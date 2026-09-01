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
        <h2 className="mb-12 font-serif text-3xl text-ink">How it works</h2>
        <div className="grid gap-10 md:grid-cols-4">
          {STAGES.map((s, i) => (
            <Reveal key={s.name} delay={i * 0.06}>
              <div className="border-t border-border pt-4">
                <span className="font-mono text-xs text-ink-muted">0{i + 1}</span>
                <h3 className="mt-2 font-serif text-xl text-ink">{s.name}</h3>
                <p className="mt-2 font-sans text-sm text-ink-muted">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
