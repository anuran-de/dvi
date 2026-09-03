import { formatDateTime, formatDuration } from '@/lib/format';

export function Timeline({ changeAt, detectedAt }: { changeAt: string; detectedAt: string }) {
  return (
    <div className="flex items-center gap-3 font-mono text-xs text-ink-muted">
      <div className="flex flex-col">
        <span className="uppercase tracking-wide">change</span>
        <span className="mt-0.5 text-ink">{formatDateTime(changeAt)}</span>
      </div>
      <div className="relative mx-1 h-px flex-1 bg-border">
        <span className="absolute left-0 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-ink-muted bg-canvas" aria-hidden />
        <span className="absolute left-1/2 -top-2.5 -translate-x-1/2 rounded-sm border border-border bg-canvas px-1.5 py-0.5">
          <span className="text-accent">{formatDuration(changeAt, detectedAt)}</span>
          <span className="ml-1 text-ink-muted">lead</span>
        </span>
        <span className="absolute right-0 top-1/2 h-2 w-2 translate-x-1/2 -translate-y-1/2 rounded-full bg-accent" aria-hidden />
      </div>
      <div className="flex flex-col text-right">
        <span className="uppercase tracking-wide">detected</span>
        <span className="mt-0.5 text-ink">{formatDateTime(detectedAt)}</span>
      </div>
    </div>
  );
}
