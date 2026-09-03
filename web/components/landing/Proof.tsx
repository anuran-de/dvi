'use client';
import { Container } from '@/components/ui/Container';
import { Stat } from '@/components/ui/Stat';
import { Reveal } from '@/components/motion/Reveal';

export function Proof() {
  return (
    <section className="py-24">
      <Container>
        <Reveal>
          <h2 className="font-serif text-3xl text-ink">Measured, not marketed</h2>
          <p className="mt-3 max-w-lg font-sans text-ink-muted">
            Every number below comes from a benchmark run, not a slide.
          </p>
        </Reveal>
        <Reveal delay={0.06}>
          <div className="mt-12 grid divide-y divide-border border-y border-border md:grid-cols-3 md:divide-x md:divide-y-0">
            <div className="py-6 md:px-8 md:py-0">
              <Stat label="Injected recall" value="100%" mono />
            </div>
            <div className="py-6 md:px-8 md:py-0">
              <Stat label="Real-vs-real false positives" value="0" mono />
            </div>
            <div className="py-6 md:px-8 md:py-0">
              <Stat label="Out-of-fold ECE" value="0.047" mono />
            </div>
          </div>
        </Reveal>
        <p className="mt-8 max-w-xl font-sans text-sm text-ink-muted">
          Validated on 53,940 rows of real data. Detection is deterministic — an
          LLM may narrate evidence, but never decides whether something changed.
        </p>
      </Container>
    </section>
  );
}
