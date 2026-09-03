'use client';
import Link from 'next/link';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

export function FooterCta() {
  return (
    <footer className="border-t border-border py-20">
      <Container>
        <Reveal>
          <div className="flex flex-col gap-10 rounded-md border border-border bg-surface p-8 md:flex-row md:items-center md:justify-between md:p-12">
            <div>
              <p className="font-serif text-2xl leading-snug text-ink md:text-3xl">
                Add DVI to your pipeline.
              </p>
              <pre className="mt-6 inline-block rounded-sm border border-border bg-canvas-raised px-4 py-2 font-mono text-sm text-ink">
                pip install dvi
              </pre>
            </div>
            <div className="flex shrink-0 flex-col items-start gap-3 md:items-end">
              <Link
                href="/incidents/"
                className="inline-flex items-center gap-2 rounded-sm bg-accent px-5 py-2.5 font-sans text-sm font-medium text-canvas transition-transform hover:-translate-y-0.5 hover:opacity-95"
              >
                See a detected incident →
              </Link>
              <a
                href="https://github.com/anuran-de/dvi"
                className="font-mono text-sm text-accent hover:underline"
              >
                github.com/anuran-de/dvi →
              </a>
            </div>
          </div>
        </Reveal>
      </Container>
    </footer>
  );
}
