export function Card({ className = '', children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={`rounded-md border border-border bg-surface ${className}`}>{children}</div>
  );
}
