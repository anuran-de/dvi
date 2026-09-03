'use client';
import { motion, useReducedMotion } from 'framer-motion';
import { MOTION } from '@/components/motion/tokens';

// The product thesis, drawn: two series that track together until one silently
// drifts — while every structural check stays green. The shared prefix is
// identical in both paths, so the "actual" line visibly peels away from the
// baseline at the divergence marker.
const SHARED = 'M0 150 C 60 140, 120 159, 180 149 C 214 143, 236 150, 250 150';
const BASELINE = `${SHARED} C 300 150, 360 150, 460 149`;
const ACTUAL = `${SHARED} C 286 149, 316 128, 356 108 C 396 88, 428 78, 460 70`;
const DIVERGE_X = 250;

const CHECKS = ['schema', 'freshness', 'row count', 'nulls'];

function Check() {
  return (
    <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden className="shrink-0">
      <path
        d="M2.5 6.2 L5 8.6 L9.5 3.6"
        fill="none"
        stroke="var(--ok)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function DivergenceMotif() {
  const reduced = useReducedMotion();
  const draw = reduced
    ? {}
    : {
        initial: { pathLength: 0, opacity: 0 },
        whileInView: { pathLength: 1, opacity: 1 },
        viewport: { once: true },
      };

  return (
    <figure className="relative" aria-label="Two data series that track together until one silently diverges while every structural check stays green">
      <div className="rounded-md border border-border bg-canvas p-5 shadow-[var(--shadow-card)]">
        <div className="mb-4 flex items-center justify-between font-mono text-[11px] uppercase tracking-widest text-ink-muted">
          <span>revenue · daily</span>
          <span className="text-ink-muted">last 30 runs</span>
        </div>

        <svg viewBox="0 0 460 200" className="w-full" role="img" aria-label="Divergence chart">
          {/* baseline gridlines */}
          {[60, 105, 150].map((y) => (
            <line key={y} x1="0" y1={y} x2="460" y2={y} stroke="var(--grid-line)" strokeWidth="1" />
          ))}

          {/* divergence marker */}
          <motion.g
            initial={reduced ? undefined : { opacity: 0 }}
            whileInView={reduced ? undefined : { opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: MOTION.base, ease: MOTION.easeOut, delay: reduced ? 0 : 1.0 }}
          >
            <line x1={DIVERGE_X} y1="24" x2={DIVERGE_X} y2="170" stroke="var(--accent)" strokeWidth="1" strokeDasharray="2 3" opacity="0.5" />
            <text x={DIVERGE_X + 6} y="34" className="font-mono" fontSize="10" fill="var(--accent)">
              drift begins
            </text>
          </motion.g>

          {/* baseline — what the number should be */}
          <motion.path
            d={BASELINE}
            fill="none"
            stroke="var(--ink-muted)"
            strokeWidth="1.5"
            strokeDasharray="3 3"
            {...draw}
            transition={{ duration: reduced ? 0 : 0.9, ease: MOTION.easeOut }}
          />

          {/* actual — what silently shipped */}
          <motion.path
            d={ACTUAL}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2.5"
            strokeLinecap="round"
            {...draw}
            transition={{ duration: reduced ? 0 : 0.9, ease: MOTION.easeOut, delay: reduced ? 0 : 0.35 }}
          />

          {/* endpoint dot on the drifted line */}
          <motion.circle
            cx="460" cy="70" r="3.5" fill="var(--accent)"
            initial={reduced ? undefined : { scale: 0, opacity: 0 }}
            whileInView={reduced ? undefined : { scale: 1, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: MOTION.base, ease: MOTION.easeOut, delay: reduced ? 0 : 1.15 }}
          />
        </svg>

        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t border-border pt-4 font-mono text-[11px] text-ink-muted">
          {CHECKS.map((c) => (
            <span key={c} className="inline-flex items-center gap-1.5">
              <Check />
              {c} OK
            </span>
          ))}
        </div>
      </div>

      <figcaption className="mt-3 font-mono text-[11px] text-ink-muted">
        Every structural check passes. The value is still wrong.
      </figcaption>
    </figure>
  );
}
