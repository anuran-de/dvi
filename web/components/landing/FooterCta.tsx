'use client';
import { Container } from '@/components/ui/Container';
import { Reveal } from '@/components/motion/Reveal';

export function FooterCta() {
  return (
    <footer className="border-t border-border py-20">
      <Container>
        <Reveal>
          <p className="font-serif text-2xl text-ink">Add DVI to your pipeline.</p>
          <pre className="mt-6 inline-block rounded-sm border border-border bg-surface px-4 py-2 font-mono text-sm text-ink">
            pip install dvi
          </pre>
          <div className="mt-6">
            <a href="https://github.com/anuran-de/dvi" className="font-mono text-sm text-accent hover:underline">
              github.com/anuran-de/dvi →
            </a>
          </div>
        </Reveal>
      </Container>
    </footer>
  );
}
