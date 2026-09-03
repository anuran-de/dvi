import type { Easing } from 'framer-motion';

export const MOTION = {
  fast: 0.16,
  base: 0.24,
  slow: 0.42,
  easeOut: [0.22, 1, 0.36, 1] as Easing,
  easeInOut: [0.65, 0, 0.35, 1] as Easing,
};
