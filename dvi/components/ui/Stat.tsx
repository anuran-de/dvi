export function Stat({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-mono text-xs uppercase tracking-wide text-ink-muted">{label}</span>
      <span className={`text-lg text-ink ${mono ? 'font-mono' : 'font-sans'}`}>{value}</span>
    </div>
  );
}
