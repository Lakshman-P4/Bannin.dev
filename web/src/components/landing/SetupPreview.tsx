'use client';

import { motion, useReducedMotion } from 'framer-motion';

const STEPS = [
  { step: '1', command: 'pip install bannin', label: 'Install the agent' },
  { step: '2', command: 'bannin start', label: 'Start monitoring' },
  { step: '3', command: 'Connect on bannin.dev', label: 'Check in from anywhere' },
] as const;

export function SetupPreview() {
  const prefersReducedMotion = useReducedMotion();
  const duration = prefersReducedMotion ? 0 : 0.4;

  return (
    <section className="py-24 px-4">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="font-display text-3xl font-bold text-text-primary mb-12">
          Up and running in three steps
        </h2>
        <div className="space-y-4">
          {STEPS.map(({ step, command, label }, i) => (
            <motion.div
              key={step}
              initial={{ opacity: prefersReducedMotion ? 1 : 0, x: prefersReducedMotion ? 0 : -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ delay: prefersReducedMotion ? 0 : i * 0.15, duration }}
              className="glass-card flex items-center gap-4 px-6 py-4 text-left"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-cyan/10 font-mono text-sm font-bold text-accent-cyan">
                {step}
              </span>
              <div>
                <code className="font-mono text-sm text-accent-cyan">{command}</code>
                <p className="text-xs text-text-muted mt-0.5">{label}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
