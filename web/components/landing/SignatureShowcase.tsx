'use client';
import { Container } from '@/components/ui/Container';
import { Card } from '@/components/ui/Card';
import { Reveal } from '@/components/motion/Reveal';

const SIGNATURES = [
  ['Value substitution', 'A category is silently renamed — "UK" → "United Kingdom".'],
  ['Distribution shift', 'A numeric column drifts beyond its historical spread.'],
  ['Cardinality change', 'The set of distinct values quietly grows or collapses.'],
  ['Format drift', 'Casing or formatting mutates under a refactor.'],
] as const;

export function SignatureShowcase() {
  return (
    <section className="border-t border-border bg-surface py-24">
      <Container>
        <Reveal>
          <h2 className="font-serif text-3xl text-ink">The signatures</h2>
          <p className="mt-3 max-w-lg font-sans text-ink-muted">
            Deterministic tests over two column profiles — each recognizes the
            statistical fingerprint of a specific kind of semantic change.
          </p>
        </Reveal>
        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {SIGNATURES.map(([title, body], i) => (
            <Reveal key={title} delay={i * 0.05}>
              <Card className="group relative overflow-hidden p-6 transition-all hover:-translate-y-0.5 hover:shadow-card">
                <div className="flex items-start justify-between gap-4">
                  <h3 className="font-mono text-sm uppercase tracking-wide text-accent">{title}</h3>
                  <span className="font-mono text-xs text-ink-muted/70">0{i + 1}</span>
                </div>
                <p className="mt-2 font-sans text-ink-muted">{body}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
