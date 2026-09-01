'use client';
import Link from 'next/link';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

export function Hero() {
  return (
    <section className="border-b border-border py-28">
      <Container>
        <Reveal delay={0}>
          <p className="mb-6 font-mono text-xs uppercase tracking-widest text-ink-muted">
            Data Versioning Intelligence
          </p>
        </Reveal>
        <Reveal delay={0.06}>
          <h1 className="max-w-3xl font-serif text-5xl leading-tight text-ink md:text-6xl">
            The silent data change, caught.
          </h1>
        </Reveal>
        <Reveal delay={0.12}>
          <p className="mt-6 max-w-xl font-sans text-lg text-ink-muted">
            Every structural check is green — schema, freshness, row count, nulls —
            and the business number is still wrong. DVI detects the semantic change,
            attributes it to the deploy, and maps the blast radius.
          </p>
        </Reveal>
        <Reveal delay={0.18}>
          <div className="mt-10 flex items-center gap-6">
            <Link
              href="/incidents/"
              className="rounded-sm bg-accent px-5 py-2.5 font-sans text-canvas transition-opacity hover:opacity-90"
            >
              See a detected incident
            </Link>
            <a
              href="https://github.com/anuran-de/dvi"
              className="font-mono text-sm text-ink underline-offset-4 hover:underline"
            >
              View on GitHub →
            </a>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
