'use client';

import { Brain } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';
import type { ConversationHealth as ConversationHealthType, HealthComponent } from '@/types';

interface ConversationHealthProps {
  health: ConversationHealthType | null;
}

const DISPLAY_COMPONENTS: ReadonlyArray<{ key: string; label: string }> = [
  { key: 'context_freshness', label: 'Context Freshness' },
  { key: 'session_fatigue', label: 'Session Fatigue' },
  { key: 'chat_quality', label: 'Output Quality' },
];

function scoreColor(score: number): string {
  if (score >= 70) return 'text-status-green';
  if (score >= 50) return 'text-status-amber';
  return 'text-status-red';
}

function barColor(score: number): string {
  if (score >= 70) return 'bg-status-green';
  if (score >= 50) return 'bg-status-amber';
  return 'bg-status-red';
}

function ratingBadge(rating: string): 'success' | 'warning' | 'danger' | 'info' {
  if (rating === 'excellent' || rating === 'good') return 'success';
  if (rating === 'fair') return 'warning';
  if (rating === 'poor' || rating === 'critical') return 'danger';
  return 'info';
}

function SignalBar({ label, component }: { label: string; component: HealthComponent }) {
  const score = Math.round(component.score);
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-xs font-medium text-text-secondary">{label}</span>
        <span className={cn('font-mono text-xs font-semibold', scoreColor(score))}>
          {score}
        </span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-surface-raised"
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${score} out of 100`}
      >
        <div
          className={cn('h-full rounded-full transition-all duration-500', barColor(score))}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      {component.detail && (
        <p className="mt-1 text-[10px] leading-tight text-text-muted">{component.detail}</p>
      )}
    </div>
  );
}

export function ConversationHealth({ health }: ConversationHealthProps) {
  if (!health) {
    return (
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Brain size={16} className="text-text-muted" aria-hidden="true" />
          <h3 className="text-sm font-medium text-text-secondary">Conversation Health</h3>
        </div>
        <p className="text-sm text-text-muted">
          Waiting for LLM activity...
        </p>
      </Card>
    );
  }

  const hasSignals = DISPLAY_COMPONENTS.some(({ key }) => key in health.components);

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-accent-cyan" aria-hidden="true" />
          <h3 className="text-sm font-medium text-text-secondary">Conversation Health</h3>
        </div>
        <Badge variant={ratingBadge(health.rating)}>{health.rating}</Badge>
      </div>

      {hasSignals ? (
        <div aria-live="polite">
          {DISPLAY_COMPONENTS.map(({ key, label }) => {
            const component = health.components[key];
            if (!component) return null;
            return <SignalBar key={key} label={label} component={component} />;
          })}
        </div>
      ) : (
        <p className="text-sm text-text-muted">No signal data available yet.</p>
      )}

      {health.recommendation && (
        <p className="mt-3 text-xs text-status-amber border-t border-surface-border pt-3">
          {health.recommendation}
        </p>
      )}
    </Card>
  );
}
