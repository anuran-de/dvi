import Link from 'next/link';
import { Container } from '@/components/ui/Container';

export default function NotFound() {
  return (
    <main className="py-24">
      <Container>
        <p className="mb-3 font-mono text-sm text-ink-muted">404</p>
        <h1 className="mb-3 font-serif text-3xl text-ink">This page could not be found</h1>
        <p className="mb-8 max-w-prose font-sans text-ink-muted">
          The page you are looking for does not exist or has moved.
        </p>
        <Link href="/incidents/" className="font-sans text-accent underline underline-offset-4">
          View detected incidents
        </Link>
      </Container>
    </main>
  );
}
