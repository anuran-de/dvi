import type { Severity } from '@/lib/types';

const BG: Record<Severity, string> = {
  low: 'bg-sev-low',
  medium: 'bg-sev-medium',
  high: 'bg-sev-high',
  critical: 'bg-sev-high',
};

export function SeverityTag({ severity }: { severity: Severity }) {
  return (
    <span
      data-severity={severity}
      className={`inline-flex items-center rounded-sm px-2 py-0.5 font-mono text-xs uppercase tracking-wide text-canvas ${BG[severity]}`}
    >
      {severity}
    </span>
  );
}
