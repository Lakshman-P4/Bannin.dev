'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { AlertTriangle, Shield } from 'lucide-react';

export function ProblemSolution() {
  const prefersReducedMotion = useReducedMotion();
  const duration = prefersReducedMotion ? 0 : 0.5;

  return (
    <section className="py-24 px-4">
      <div className="mx-auto grid max-w-5xl gap-8 md:grid-cols-2">
        <motion.div
          initial={{ opacity: prefersReducedMotion ? 1 : 0, x: prefersReducedMotion ? 0 : -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration }}
          className="glass-card p-8"
        >
          <div className="mb-4 flex items-center gap-2 text-status-red">
            <AlertTriangle size={20} aria-hidden="true" />
            <h2 className="font-display text-xl font-semibold">The Problem</h2>
          </div>
          <p className="text-text-secondary leading-relaxed">
            Your training OOMs at hour 3. Your Colab session disconnects.
            Your GPU runs out of VRAM. You don&apos;t find out until you get back.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: prefersReducedMotion ? 1 : 0, x: prefersReducedMotion ? 0 : 20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration, delay: prefersReducedMotion ? 0 : 0.15 }}
          className="glass-card p-8"
        >
          <div className="mb-4 flex items-center gap-2 text-status-green">
            <Shield size={20} aria-hidden="true" />
            <h2 className="font-display text-xl font-semibold">The Solution</h2>
          </div>
          <p className="text-text-secondary leading-relaxed">
            Bannin runs in the background. It predicts crashes before they happen.
            It sends you a notification. You check in from any browser.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
