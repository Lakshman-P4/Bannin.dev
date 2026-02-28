'use client';

import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { formatRelativeTime } from '@/lib/utils';
import type { AgentEvent } from '@/types';

interface EventFeedProps {
  events: AgentEvent[];
}

const severityIcon = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

const severityColor = {
  critical: 'text-status-red',
  warning: 'text-status-amber',
  info: 'text-accent-cyan',
} as const;

export function EventFeed({ events }: EventFeedProps) {
  return (
    <Card>
      <h3 className="text-sm font-medium text-text-secondary mb-3">Recent Events</h3>
      {events.length === 0 ? (
        <p className="text-sm text-text-muted">No events yet.</p>
      ) : (
        <ul className="space-y-2" aria-label="Recent events">
          {events.slice(0, 10).map((event) => {
            const Icon = severityIcon[event.severity] ?? Info;
            const color = severityColor[event.severity] ?? 'text-text-muted';
            return (
              <li key={event.id} className="flex items-start gap-2.5 py-1">
                <Icon size={14} className={`mt-0.5 shrink-0 ${color}`} aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-text-primary truncate">{event.message}</p>
                </div>
                <time className="shrink-0 text-xs text-text-muted font-mono">
                  {formatRelativeTime(event.timestamp)}
                </time>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
