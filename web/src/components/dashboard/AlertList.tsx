'use client';

import { AlertCircle, AlertTriangle, Info, X } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { formatRelativeTime } from '@/lib/utils';
import { useDashboardStore } from '@/stores/dashboardStore';
import type { Alert } from '@/types';

interface AlertListProps {
  alerts: Alert[];
}

const severityIcon = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

const severityBadge = {
  critical: 'danger',
  warning: 'warning',
  info: 'info',
} as const;

export function AlertList({ alerts }: AlertListProps) {
  const dismissAlert = useDashboardStore((s) => s.dismissAlert);

  if (alerts.length === 0) {
    return (
      <Card>
        <h3 className="text-sm font-medium text-text-secondary mb-3">Active Alerts</h3>
        <p className="text-sm text-text-muted">All clear -- no alerts right now.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="text-sm font-medium text-text-secondary mb-3">
        Active Alerts ({alerts.length})
      </h3>
      <ul className="space-y-2" aria-label="Active alerts">
        {alerts.slice(0, 10).map((alert) => {
          const Icon = severityIcon[alert.severity];
          return (
            <li
              key={alert.id}
              className="flex items-start gap-2.5 rounded-lg bg-surface-raised/50 p-3"
            >
              <Icon size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-text-primary">{alert.message}</p>
                <span className="text-xs text-text-muted">{formatRelativeTime(alert.firedAt)}</span>
              </div>
              <Badge variant={severityBadge[alert.severity]}>
                {alert.severity}
              </Badge>
              <button
                onClick={() => dismissAlert(alert.id)}
                className="shrink-0 rounded p-0.5 text-text-muted hover:text-text-primary hover:bg-surface-border/30 transition-colors"
                aria-label={`Dismiss alert: ${alert.message}`}
              >
                <X size={14} aria-hidden="true" />
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
