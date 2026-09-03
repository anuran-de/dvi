export function Card({
  className = '',
  raised = false,
  children,
}: {
  className?: string;
  raised?: boolean;
  children: React.ReactNode;
}) {
  const surface = raised ? 'bg-canvas-raised shadow-card' : 'bg-surface';
  return <div className={`rounded-md border border-border ${surface} ${className}`}>{children}</div>;
}
