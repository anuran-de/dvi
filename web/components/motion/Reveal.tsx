'use client';
import { motion, useReducedMotion } from 'framer-motion';
import { MOTION } from './tokens';

export function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const reduced = useReducedMotion();
  if (reduced) return <div>{children}</div>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-10% 0px' }}
      transition={{ duration: MOTION.base, ease: MOTION.easeOut, delay }}
    >
      {children}
    </motion.div>
  );
}
