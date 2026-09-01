'use client';
import { Container } from '@/components/ui/Container';
import { Card } from '@/components/ui/Card';
import { Reveal } from '@/components/motion/Reveal';

const SIGNATURES = [
  ['Value substitution', 'A category is silently renamed — "UK" → "United Kingdom".'],
  ['Distribution shift', 'A numeric column drifts beyond its historical spread.'],
  ['Cardinality change', 'The set of distinct values quietly grows or collapses.'],
  ['Format drift', 'Casing or formatting mutates under a refactor.'],
];

export function SignatureShowcase() {
  return (
    <section className="border-t border-border bg-surface py-24">
      <Container>
        <h2 className="mb-12 font-serif text-3xl text-ink">The signatures</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {SIGNATURES.map(([title, body], i) => (
            <Reveal key={title} delay={i * 0.05}>
              <Card className="p-6">
                <h3 className="font-mono text-sm uppercase tracking-wide text-accent">{title}</h3>
                <p className="mt-2 font-sans text-ink-muted">{body}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
