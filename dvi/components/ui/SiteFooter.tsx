import Link from 'next/link';
import { Container } from './Container';

export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <Container>
        <div className="flex flex-col gap-4 py-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-baseline gap-3">
            <Link href="/" className="font-serif text-base text-ink">DVI</Link>
            <span className="font-mono text-xs text-ink-muted">
              Deterministic semantic change detection.
            </span>
          </div>
          <nav className="flex items-center gap-6 font-mono text-xs text-ink-muted">
            <Link href="/incidents/" className="hover:text-ink">Incidents</Link>
            <a href="https://github.com/anuran-de/dvi" className="hover:text-ink">GitHub</a>
            <span>MIT</span>
          </nav>
        </div>
      </Container>
    </footer>
  );
}
