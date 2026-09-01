'use client';
import { Container } from '@/components/ui/Container';
import { Stat } from '@/components/ui/Stat';
import { Reveal } from '@/components/motion/Reveal';

export function Proof() {
  return (
    <section className="py-24">
      <Container>
        <h2 className="mb-12 font-serif text-3xl text-ink">Measured, not marketed</h2>
        <Reveal>
          <div className="grid gap-10 md:grid-cols-3">
            <Stat label="Injected recall" value="100%" mono />
            <Stat label="Real-vs-real false positives" value="0" mono />
            <Stat label="Out-of-fold ECE" value="0.047" mono />
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
