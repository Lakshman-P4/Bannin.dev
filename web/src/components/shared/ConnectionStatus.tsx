'use client';

import { useDashboardStore } from '@/stores/dashboardStore';
import { cn } from '@/lib/utils';

export function ConnectionStatus() {
  const isConnected = useDashboardStore((s) => s.isConnected);

  return (
    <div
      className="flex items-center gap-1.5"
      role="status"
      aria-live="polite"
      aria-label={isConnected ? 'Connected to relay' : 'Disconnected from relay'}
    >
      <span
        className={cn(
          'h-2 w-2 rounded-full',
          isConnected ? 'bg-status-green animate-pulse' : 'bg-status-red',
        )}
        aria-hidden="true"
      />
      <span className="text-xs text-text-muted">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}
