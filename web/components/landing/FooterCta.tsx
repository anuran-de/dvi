'use client';
import { useState } from 'react';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

export function FooterCta() {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText('pip install dvi');
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable — the command is visible to select manually */
    }
  }

  return (
    <section className="relative overflow-hidden border-t border-border bg-surface py-20">
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" aria-hidden />
      <Container className="relative">
        <Reveal>
          <p className="font-serif text-3xl tracking-tight text-ink">
            Add DVI to your pipeline.
          </p>
          <p className="mt-3 max-w-md font-sans text-ink-muted">
            One command, deterministic detection, a pull-request comment when a number silently moves.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <div className="inline-flex items-stretch overflow-hidden rounded-sm border border-border bg-canvas">
              <code className="px-4 py-2.5 font-mono text-sm text-ink">
                <span className="select-none text-ink-muted">$ </span>pip install dvi
              </code>
              <button
                onClick={copy}
                aria-label="Copy install command"
                className="border-l border-border px-3 font-mono text-xs uppercase tracking-wide text-ink-muted transition-colors hover:bg-accent-wash hover:text-accent"
              >
                {copied ? 'copied' : 'copy'}
              </button>
            </div>
            <a
              href="https://github.com/anuran-de/dvi"
              className="link-underline font-mono text-sm text-accent"
            >
              github.com/anuran-de/dvi
            </a>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
