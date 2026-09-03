'use client';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

const STATS = [
  { label: 'Injected recall', value: '100%' },
  { label: 'Real-vs-real false positives', value: '0' },
  { label: 'Out-of-fold ECE', value: '0.047' },
];

export function Proof() {
  return (
    <section className="py-24">
      <Container>
        <Reveal>
          <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-muted">Evidence</p>
          <h2 className="mb-12 font-serif text-3xl tracking-tight text-ink">Measured, not marketed</h2>
        </Reveal>
        <Reveal>
          <dl className="grid overflow-hidden rounded-md border border-border md:grid-cols-3">
            {STATS.map((s, i) => (
              <div
                key={s.label}
                className={`bg-canvas px-6 py-8 ${i > 0 ? 'border-t border-border md:border-l md:border-t-0' : ''}`}
              >
                <dd className="font-mono text-4xl tabular-nums tracking-tight text-ink md:text-5xl">
                  {s.value}
                </dd>
                <dt className="mt-3 font-mono text-xs uppercase tracking-wide text-ink-muted">
                  {s.label}
                </dt>
              </div>
            ))}
          </dl>
        </Reveal>
        <p className="mt-8 max-w-xl font-sans text-sm leading-relaxed text-ink-muted">
          Validated on 53,940 rows of real data. Detection is deterministic — an
          LLM may narrate evidence, but never decides whether something changed.
        </p>
      </Container>
    </section>
  );
}
