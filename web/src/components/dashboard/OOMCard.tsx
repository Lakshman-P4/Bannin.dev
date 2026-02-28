'use client';

import { AlertTriangle, CheckCircle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import type { OOMPrediction } from '@/types';
import { cn } from '@/lib/utils';

interface OOMCardProps {
  prediction: OOMPrediction | null;
}

export function OOMCard({ prediction }: OOMCardProps) {
  const ram = prediction?.ram;
  const severity = ram?.severity ?? 'ok';
  const isOk = severity === 'ok';

  const urgency = severity === 'critical' ? 'critical' : severity === 'warning' ? 'warning' : 'normal';

  const badgeVariant = severity === 'critical' ? 'danger' : severity === 'warning' ? 'warning' : 'success';

  // When memory is high but trend is stable, OOM severity is "ok" but the
  // user should still see that headroom is low.
  const highButStable = isOk && ram != null && ram.currentPercent >= 85;
  const effectiveUrgency = highButStable ? 'warning' as const : urgency;

  let message: string;
  if (!prediction || !ram) {
    message = 'Waiting for enough data to make a prediction.';
  } else if (highButStable) {
    const headroom = Math.round(100 - ram.currentPercent);
    message = `Memory is high but stable -- only ${headroom}% headroom remaining.`;
  } else if (isOk) {
    message = 'Looking good -- no memory pressure detected.';
  } else if (ram.minutesUntilFull !== null) {
    const mins = Math.round(ram.minutesUntilFull);
    message = `Memory will be full in ~${mins} minute${mins !== 1 ? 's' : ''}.`;
  } else {
    message = 'Memory is under pressure but timing is uncertain.';
  }

  const effectiveBadge = highButStable ? 'warning' : badgeVariant;
  const effectiveLabel = highButStable ? 'low headroom' : severity;

  return (
    <Card urgency={effectiveUrgency}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-text-secondary">OOM Prediction</h3>
        <Badge variant={effectiveBadge}>{effectiveLabel}</Badge>
      </div>
      <div className="flex items-start gap-3">
        {isOk && !highButStable ? (
          <CheckCircle size={20} className="mt-0.5 shrink-0 text-status-green" aria-hidden="true" />
        ) : (
          <AlertTriangle
            size={20}
            className={cn(
              'mt-0.5 shrink-0',
              severity === 'critical' ? 'text-status-red' : 'text-status-amber',
            )}
            aria-hidden="true"
          />
        )}
        <div>
          <p className="text-sm text-text-primary" role="status" aria-live="polite">
            {message}
          </p>
          {ram && ram.confidence > 0 && (
            <p className="mt-1 text-xs text-text-muted font-mono">
              Confidence: {Math.round(ram.confidence)}% | Current: {Math.round(ram.currentPercent)}%
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
