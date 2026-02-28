'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { Button } from '@/components/ui/Button';
import { BanninEye } from '@/components/shared/BanninEye';

const words = ['You hit run.', 'You walk away.', 'Then what?'];

export function Hero() {
  const prefersReducedMotion = useReducedMotion();
  const baseDelay = prefersReducedMotion ? 0 : 0.3;
  const wordDelay = prefersReducedMotion ? 0 : 0.4;
  const duration = prefersReducedMotion ? 0 : 0.6;

  return (
    <section className="relative flex min-h-screen items-center justify-center gradient-mesh px-4">
      <div className="mx-auto max-w-3xl text-center">
        <motion.div
          initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0, duration: prefersReducedMotion ? 0 : 0.8, ease: 'easeOut' }}
          className="mb-8 flex justify-center"
        >
          <BanninEye size={120} />
        </motion.div>

        <h1 className="font-display text-4xl font-bold leading-tight tracking-tight text-text-primary sm:text-5xl md:text-6xl">
          {words.map((word, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: baseDelay + i * wordDelay, duration }}
              className="inline-block mr-2"
            >
              {word}
            </motion.span>
          ))}
        </h1>

        <motion.p
          initial={{ opacity: prefersReducedMotion ? 1 : 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: prefersReducedMotion ? 0 : 1.6, duration }}
          className="mx-auto mt-6 max-w-xl text-base text-text-secondary sm:text-lg"
        >
          Bannin watches your machine, your training runs, and your AI tools.
          Get alerts before things crash. Check in from anywhere. Zero setup.
        </motion.p>

        <motion.div
          initial={{ opacity: prefersReducedMotion ? 1 : 0, y: prefersReducedMotion ? 0 : 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: prefersReducedMotion ? 0 : 2.0, duration: prefersReducedMotion ? 0 : 0.5 }}
          className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
        >
          <Link href="/register">
            <Button size="lg">Get Started Free</Button>
          </Link>
          <a href="#features">
            <Button variant="ghost" size="lg">
              See How It Works
            </Button>
          </a>
        </motion.div>
      </div>
    </section>
  );
}
