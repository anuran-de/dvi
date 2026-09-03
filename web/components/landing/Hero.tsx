'use client';
import Link from 'next/link';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';
import { DivergenceMotif } from './DivergenceMotif';

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-border">
      <div className="bg-grid pointer-events-none absolute inset-0" aria-hidden />
      <Container className="relative">
        <div className="grid items-center gap-16 py-24 md:grid-cols-[1.05fr_0.95fr] md:py-28">
          <div>
            <Reveal delay={0}>
              <p className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-ink-muted">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
                Data Versioning Intelligence
              </p>
            </Reveal>
            <Reveal delay={0.06}>
              <h1 className="max-w-2xl font-serif text-5xl leading-[1.05] tracking-tight text-ink md:text-6xl">
                The silent data change, <span className="italic text-accent">caught</span>.
              </h1>
            </Reveal>
            <Reveal delay={0.12}>
              <p className="mt-6 max-w-xl font-sans text-lg leading-relaxed text-ink-muted">
                Every structural check is green — schema, freshness, row count, nulls —
                and the business number is still wrong. DVI detects the semantic change,
                attributes it to the deploy, and maps the blast radius.
              </p>
            </Reveal>
            <Reveal delay={0.18}>
              <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-4">
                <Link
                  href="/incidents/"
                  className="group inline-flex items-center gap-2 rounded-sm bg-accent px-5 py-2.5 font-sans text-canvas shadow-[var(--shadow-card)] transition-all hover:bg-accent-strong hover:shadow-[var(--shadow-lift)]"
                >
                  See a detected incident
                  <span className="transition-transform group-hover:translate-x-0.5" aria-hidden>→</span>
                </Link>
                <a
                  href="https://github.com/anuran-de/dvi"
                  className="link-underline font-mono text-sm text-ink"
                >
                  View on GitHub
                </a>
              </div>
            </Reveal>
          </div>

          <Reveal delay={0.1}>
            <DivergenceMotif />
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
