'use client';
import { motion, useReducedMotion } from 'framer-motion';
import { MOTION } from '@/components/motion/tokens';

const STRUCTURAL = ['Schema', 'Freshness', 'Row count', 'Nulls'];

function CheckGlyph() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
      <path d="M1.5 5.2 L4 7.8 L8.5 2.2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function FlagGlyph() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
      <path d="M2 1v8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M2 1.5h5.5L6 3.5l1.5 2H2" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

/**
 * The signature visual: every structural check is green, and the one thing
 * that matters — the business number — silently flips to wrong. This is the
 * whole thesis of DVI rendered as a strip of pills.
 */
export function ChecksMotif() {
  const reduced = useReducedMotion();

  return (
    <div
      role="img"
      aria-label="All structural checks pass — schema, freshness, row count, and nulls are green — while the business number is silently wrong"
      className="flex flex-wrap items-center gap-2"
    >
      {STRUCTURAL.map((label, i) => (
        <motion.span
          key={label}
          initial={reduced ? undefined : { opacity: 0, y: 6 }}
          whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: MOTION.base, ease: MOTION.easeOut, delay: i * 0.05 }}
          className="inline-flex items-center gap-1.5 rounded-sm border border-sev-low/30 bg-sev-low-soft px-2.5 py-1 font-mono text-[11px] uppercase tracking-wide text-sev-low"
        >
          <CheckGlyph />
          {label}
        </motion.span>
      ))}
      <span aria-hidden="true" className="mx-0.5 text-ink-muted">
        +
      </span>
      <motion.span
        initial={reduced ? undefined : { opacity: 0, y: 6 }}
        whileInView={
          reduced
            ? undefined
            : {
                opacity: 1,
                y: 0,
                borderColor: ['rgba(63,122,94,0.3)', 'rgba(162,59,52,0.4)'],
                backgroundColor: ['var(--sev-low-soft)', 'var(--sev-high-soft)'],
                color: ['var(--sev-low)', 'var(--sev-high)'],
              }
        }
        viewport={{ once: true }}
        transition={
          reduced
            ? undefined
            : {
                duration: MOTION.base,
                ease: MOTION.easeOut,
                delay: 0.2,
                borderColor: { delay: 0.9, duration: MOTION.slow, ease: MOTION.easeInOut },
                backgroundColor: { delay: 0.9, duration: MOTION.slow, ease: MOTION.easeInOut },
                color: { delay: 0.9, duration: MOTION.slow, ease: MOTION.easeInOut },
              }
        }
        className="inline-flex items-center gap-1.5 rounded-sm border border-sev-high/40 bg-sev-high-soft px-2.5 py-1 font-mono text-[11px] uppercase tracking-wide text-sev-high"
      >
        <FlagGlyph />
        Business number: wrong
      </motion.span>
    </div>
  );
}
