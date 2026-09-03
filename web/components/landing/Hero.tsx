'use client';
import Link from 'next/link';
import type { IncidentDetail } from '@/lib/types';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';
import { ChecksMotif } from '@/components/landing/ChecksMotif';
import { IncidentSpecimen } from '@/components/landing/IncidentSpecimen';

export function Hero({ specimen = null }: { specimen?: IncidentDetail | null }) {
  return (
    <section className="relative overflow-hidden border-b border-border py-24 md:py-32">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-grid bg-[length:56px_56px] [mask-image:linear-gradient(to_bottom,black,transparent_75%)] opacity-[0.35]"
      />
      <Container className="relative">
        <div className="grid gap-16 lg:grid-cols-[1.15fr_0.85fr] lg:items-start">
          <div>
            <Reveal delay={0}>
              <p className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-ink-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
                Data Versioning Intelligence
              </p>
            </Reveal>
            <Reveal delay={0.06}>
              <h1 className="max-w-2xl font-serif text-5xl leading-[1.05] tracking-tight text-ink md:text-6xl lg:text-[3.75rem]">
                The silent data change your dashboards missed.
              </h1>
            </Reveal>
            <Reveal delay={0.12}>
              <p className="mt-6 max-w-xl font-sans text-lg leading-relaxed text-ink-muted">
                Schema, freshness, row count, and nulls are all green — and a business
                number is still wrong. DVI detects the semantic change, attributes it
                to the deploy, and maps the blast radius before finance does.
              </p>
            </Reveal>
            <Reveal delay={0.16}>
              <div className="mt-8">
                <ChecksMotif />
              </div>
            </Reveal>
            <Reveal delay={0.22}>
              <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4">
                <Link
                  href="/incidents/"
                  className="group inline-flex items-center gap-2 rounded-sm bg-accent px-5 py-2.5 font-sans text-sm font-medium text-canvas transition-transform hover:-translate-y-0.5 hover:opacity-95"
                >
                  See a detected incident
                  <span aria-hidden="true" className="transition-transform group-hover:translate-x-0.5">
                    →
                  </span>
                </Link>
                <a
                  href="https://github.com/anuran-de/dvi"
                  className="font-mono text-sm text-ink underline-offset-4 hover:underline"
                >
                  View on GitHub
                </a>
              </div>
            </Reveal>
          </div>

          {specimen && (
            <Reveal delay={0.28}>
              <div>
                <p className="mb-3 font-mono text-xs uppercase tracking-widest text-ink-muted">
                  Real detection, not a mockup
                </p>
                <IncidentSpecimen incident={specimen} />
              </div>
            </Reveal>
          )}
        </div>
      </Container>
    </section>
  );
}
