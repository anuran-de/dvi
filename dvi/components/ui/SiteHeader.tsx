import Link from 'next/link';
import { Container } from './Container';

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-canvas">
      <Container>
        <div className="flex h-14 items-center justify-between">
          <Link href="/" className="group inline-flex items-baseline gap-2" aria-label="DVI home">
            <span className="font-serif text-lg tracking-tight text-ink">DVI</span>
            <span className="hidden font-mono text-[11px] uppercase tracking-widest text-ink-muted sm:inline">
              Data Versioning Intelligence
            </span>
          </Link>
          <nav className="flex items-center gap-6 font-mono text-sm">
            <Link href="/incidents/" className="link-underline text-ink">Incidents</Link>
            <a
              href="https://github.com/anuran-de/dvi"
              className="link-underline text-ink-muted hover:text-ink"
            >
              GitHub
            </a>
          </nav>
        </div>
      </Container>
    </header>
  );
}
