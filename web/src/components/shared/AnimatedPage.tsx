'use client';

import { motion, useReducedMotion } from 'framer-motion';
import type { ReactNode } from 'react';

interface AnimatedPageProps {
  children: ReactNode;
  className?: string;
}

const pageVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0 },
};

const instantVariants = {
  hidden: { opacity: 1, y: 0 },
  visible: { opacity: 1, y: 0 },
};

export function AnimatedPage({ children, className }: AnimatedPageProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={prefersReducedMotion ? instantVariants : pageVariants}
      transition={{ duration: prefersReducedMotion ? 0 : 0.3, ease: 'easeOut' }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
