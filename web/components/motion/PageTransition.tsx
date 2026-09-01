'use client';
import { motion, useReducedMotion } from 'framer-motion';
import { usePathname } from 'next/navigation';
import { MOTION } from './tokens';

export function PageTransition({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  const pathname = usePathname();
  if (reduced) return <>{children}</>;
  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: MOTION.base, ease: MOTION.easeOut }}
    >
      {children}
    </motion.div>
  );
}
