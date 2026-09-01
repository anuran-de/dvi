export function EvidenceList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1 font-mono text-sm text-ink">
      {items.map((line, i) => (
        <li key={i} className="flex gap-2">
          <span className="select-none text-ink-muted">›</span>
          <span>{line}</span>
        </li>
      ))}
    </ul>
  );
}
