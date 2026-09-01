import { formatDateTime, formatDuration } from '@/lib/format';

export function Timeline({ changeAt, detectedAt }: { changeAt: string; detectedAt: string }) {
  return (
    <div className="flex items-center gap-3 font-mono text-xs text-ink-muted">
      <div className="flex flex-col">
        <span className="uppercase tracking-wide">change</span>
        <span className="text-ink">{formatDateTime(changeAt)}</span>
      </div>
      <div className="relative h-px flex-1 bg-border">
        <span className="absolute left-1/2 -top-2 -translate-x-1/2 rounded-sm bg-canvas px-1 text-accent">
          {formatDuration(changeAt, detectedAt)}
        </span>
      </div>
      <div className="flex flex-col text-right">
        <span className="uppercase tracking-wide">detected</span>
        <span className="text-ink">{formatDateTime(detectedAt)}</span>
      </div>
    </div>
  );
}
