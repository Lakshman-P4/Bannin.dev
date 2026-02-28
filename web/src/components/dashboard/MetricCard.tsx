'use client';

import { Card } from '@/components/ui/Card';
import { getUrgencyLevel, formatPercent, cn } from '@/lib/utils';

interface MetricCardProps {
  label: string;
  value: number | null;
  icon: React.ReactNode;
}

const urgencyColor = {
  normal: 'text-accent-cyan',
  warning: 'text-status-amber',
  critical: 'text-status-red',
} as const;

const barColor = {
  normal: 'bg-accent-cyan',
  warning: 'bg-status-amber',
  critical: 'bg-status-red',
} as const;

export function MetricCard({ label, value, icon }: MetricCardProps) {
  const percent = value ?? 0;
  const urgency = getUrgencyLevel(percent);
  const displayValue = value !== null ? formatPercent(percent) : '--';

  return (
    <Card urgency={urgency} className="relative overflow-hidden">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-text-secondary">{label}</span>
        <span className="text-text-muted" aria-hidden="true">
          {icon}
        </span>
      </div>
      <p
        className={cn('font-mono text-2xl font-bold', urgencyColor[urgency])}
        aria-live={urgency === 'critical' ? 'assertive' : 'polite'}
        aria-label={`${label}: ${displayValue}`}
      >
        {displayValue}
      </p>
      <div
        className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-surface-raised"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} usage`}
      >
        <div
          className={cn('h-full rounded-full transition-all duration-500', barColor[urgency])}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </Card>
  );
}
