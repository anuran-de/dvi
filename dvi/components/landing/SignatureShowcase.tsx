'use client';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

const SIGNATURES = [
  ['Value substitution', 'A category is silently renamed — "UK" → "United Kingdom".'],
  ['Distribution shift', 'A numeric column drifts beyond its historical spread.'],
  ['Cardinality change', 'The set of distinct values quietly grows or collapses.'],
  ['Format drift', 'Casing or formatting mutates under a refactor.'],
];

export function SignatureShowcase() {
  return (
    <section className="relative overflow-hidden border-y border-border bg-surface py-24">
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" aria-hidden />
      <Container className="relative">
        <Reveal>
          <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-muted">What DVI sees</p>
          <h2 className="mb-12 font-serif text-3xl tracking-tight text-ink">The signatures</h2>
        </Reveal>
        <div className="grid gap-4 md:grid-cols-2">
          {SIGNATURES.map(([title, body], i) => (
            <Reveal key={title} delay={i * 0.05}>
              <div className="group relative h-full rounded-md border border-border bg-canvas p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:shadow-[var(--shadow-card)]">
                <span className="absolute right-5 top-5 font-mono text-xs text-border transition-colors group-hover:text-accent">
                  0{i + 1}
                </span>
                <span className="block h-px w-8 bg-accent transition-all duration-200 group-hover:w-12" aria-hidden />
                <h3 className="mt-4 font-mono text-sm uppercase tracking-wide text-accent">{title}</h3>
                <p className="mt-2 font-sans leading-relaxed text-ink-muted">{body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
