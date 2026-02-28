'use client';

import { motion, useReducedMotion } from 'framer-motion';

const STATS = [
  { value: '30+', label: 'LLM models tracked', detail: 'OpenAI, Anthropic, Google, Ollama' },
  { value: '17', label: 'Alert rules running', detail: 'CPU, RAM, GPU, disk, session health' },
  { value: '12 min', label: 'Avg OOM lead time', detail: 'Predicted before it happens' },
  { value: '< 2 min', label: 'Setup to first alert', detail: 'pip install to production monitoring' },
] as const;

export function ProofStats() {
  const prefersReducedMotion = useReducedMotion();
  const duration = prefersReducedMotion ? 0 : 0.45;

  return (
    <section className="py-24 px-4">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center font-display text-3xl font-bold text-text-primary mb-12">
          By the numbers
        </h2>
        <div className="grid gap-6 grid-cols-2 lg:grid-cols-4">
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.value}
              initial={{ opacity: prefersReducedMotion ? 1 : 0, y: prefersReducedMotion ? 0 : 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ delay: prefersReducedMotion ? 0 : i * 0.1, duration }}
              className="glass-card p-6 text-center"
            >
              <p className="font-display text-3xl font-bold text-accent-cyan mb-1">
                {stat.value}
              </p>
              <p className="text-sm font-medium text-text-primary mb-1">
                {stat.label}
              </p>
              <p className="text-xs text-text-muted">
                {stat.detail}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
