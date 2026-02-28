'use client';

import { motion, useReducedMotion } from 'framer-motion';

const SCENARIOS = [
  {
    text: 'Your 8-hour fine-tune OOMs at hour 7. You find out at hour 10.',
    accent: 'text-status-red',
    border: 'border-status-red/15',
  },
  {
    text: 'Your Colab session expires. Your model weights are gone.',
    accent: 'text-status-amber',
    border: 'border-status-amber/15',
  },
  {
    text: 'You push a 3-hour training run and leave for lunch. It crashed 4 minutes in.',
    accent: 'text-status-red',
    border: 'border-status-red/15',
  },
  {
    text: 'Your GPU VRAM is full. Your next job silently queues. You wait for nothing.',
    accent: 'text-status-amber',
    border: 'border-status-amber/15',
  },
] as const;

export function Nightmares() {
  const prefersReducedMotion = useReducedMotion();
  const duration = prefersReducedMotion ? 0 : 0.45;

  return (
    <section className="py-24 px-4">
      <div className="mx-auto max-w-3xl">
        <h2 className="text-center font-display text-3xl font-bold text-text-primary mb-4">
          Sound familiar?
        </h2>
        <p className="text-center text-sm text-text-muted mb-12">
          Every developer has been here. Most find out too late.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {SCENARIOS.map((scenario, i) => (
            <motion.div
              key={i}
              initial={{ opacity: prefersReducedMotion ? 1 : 0, y: prefersReducedMotion ? 0 : 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ delay: prefersReducedMotion ? 0 : i * 0.1, duration }}
              className={`glass-card border ${scenario.border} p-6`}
            >
              <p className={`text-sm leading-relaxed font-medium ${scenario.accent}`}>
                &ldquo;{scenario.text}&rdquo;
              </p>
            </motion.div>
          ))}
        </div>
        <motion.p
          initial={{ opacity: prefersReducedMotion ? 1 : 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: '-20px' }}
          transition={{ delay: prefersReducedMotion ? 0 : 0.5, duration }}
          className="text-center text-sm text-text-secondary mt-8"
        >
          Bannin makes sure you never find out late again.
        </motion.p>
      </div>
    </section>
  );
}
