export function formatPercent(v: number | null): string {
  return v === null ? '—' : `${Math.round(v * 100)}%`;
}

export function formatDateTime(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

export function formatDuration(fromIso: string, toIso: string): string {
  if (!fromIso || !toIso) return '—';
  const ms = new Date(toIso).getTime() - new Date(fromIso).getTime();
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem ? `${hrs}h ${rem}m` : `${hrs}h`;
}
