'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { BrainCircuit, Globe, Zap } from 'lucide-react';
import { Card } from '@/components/ui/Card';

const FEATURES = [
  {
    icon: BrainCircuit,
    title: 'Predict, Don\'t React',
    description:
      'OOM prediction with confidence scores. Know 12 minutes before your training crashes.',
  },
  {
    icon: Globe,
    title: 'Check In From Anywhere',
    description:
      'Real-time dashboard in your browser. Metrics, alerts, training progress -- all live.',
  },
  {
    icon: Zap,
    title: 'Two Minutes to Set Up',
    description:
      'pip install bannin && bannin start. Connect to the web. Done.',
  },
] as const;

export function Features() {
  const prefersReducedMotion = useReducedMotion();
  const duration = prefersReducedMotion ? 0 : 0.5;

  return (
    <section id="features" className="py-24 px-4">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center font-display text-3xl font-bold text-text-primary mb-12">
          Built for developers who walk away
        </h2>
        <div className="grid gap-6 md:grid-cols-3">
          {FEATURES.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: prefersReducedMotion ? 1 : 0, y: prefersReducedMotion ? 0 : 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ delay: prefersReducedMotion ? 0 : i * 0.12, duration }}
            >
              <Card hoverable className="h-full">
                <feature.icon
                  size={28}
                  className="mb-4 text-accent-cyan"
                  aria-hidden="true"
                />
                <h3 className="font-display text-lg font-semibold text-text-primary mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {feature.description}
                </p>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
