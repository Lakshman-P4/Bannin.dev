'use client';

import { useState, useMemo } from 'react';
import { AlertCircle, AlertTriangle, Info, ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { formatDate } from '@/lib/utils';
import type { AgentEvent } from '@/types';

interface EventListProps {
  events: AgentEvent[];
  isLoading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
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

const GROUP_WINDOW_MS = 10 * 60 * 1000; // 10 minutes

/** Normalize alert messages so e.g. "RAM HIGH: 88.2% used" and "RAM HIGH: 85.6% used" group together. */
function normalizeMessage(message: string): string {
  return message.replace(/[\d.]+%/g, 'N%').replace(/[\d.]+/g, 'N');
}

interface EventGroup {
  key: string;
  latest: AgentEvent;
  events: AgentEvent[];
}

function groupEvents(events: AgentEvent[]): EventGroup[] {
  const groups: EventGroup[] = [];

  for (const event of events) {
    const normalized = normalizeMessage(event.message);
    const eventTime = new Date(event.timestamp).getTime();
    const groupKey = `${event.type}::${event.severity}::${normalized}`;

    // Try to find an existing group within the time window
    const existingGroup = groups.find((g) => {
      if (g.key !== groupKey) return false;
      const latestTime = new Date(g.latest.timestamp).getTime();
      return Math.abs(eventTime - latestTime) <= GROUP_WINDOW_MS;
    });

    if (existingGroup) {
      existingGroup.events.push(event);
      // Keep the most recent as "latest"
      if (eventTime > new Date(existingGroup.latest.timestamp).getTime()) {
        existingGroup.latest = event;
      }
    } else {
      groups.push({ key: groupKey, latest: event, events: [event] });
    }
  }

  return groups;
}

function EventRow({ event }: { event: AgentEvent }) {
  const Icon = severityIcon[event.severity] ?? Info;
  return (
    <div className="flex items-start gap-3 py-3">
      <Icon size={16} className="mt-0.5 shrink-0 text-text-muted" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-text-primary">{event.message}</p>
        <div className="mt-1 flex items-center gap-2 text-xs text-text-muted">
          <span className="font-mono">{formatDate(event.timestamp)}</span>
          <span className="text-surface-border">|</span>
          <span>{event.type}</span>
        </div>
      </div>
      <Badge variant={severityBadge[event.severity]}>
        {event.severity}
      </Badge>
    </div>
  );
}

function GroupedEventRow({ group }: { group: EventGroup }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = severityIcon[group.latest.severity] ?? Info;
  const count = group.events.length;

  if (count === 1) {
    return <EventRow event={group.latest} />;
  }

  // Sort events in the group by timestamp descending for expanded view
  const sorted = [...group.events].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );

  return (
    <div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-3 py-3 text-left hover:bg-surface-raised/30 -mx-1 px-1 rounded transition-colors"
        aria-expanded={expanded}
      >
        <Icon size={16} className="mt-0.5 shrink-0 text-text-muted" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-text-primary">{group.latest.message}</p>
          <div className="mt-1 flex items-center gap-2 text-xs text-text-muted">
            <span className="font-mono">{formatDate(group.latest.timestamp)}</span>
            <span className="text-surface-border">|</span>
            <span>{group.latest.type}</span>
            <span className="text-surface-border">|</span>
            <span className="text-accent-cyan">{count} occurrences</span>
          </div>
        </div>
        <Badge variant={severityBadge[group.latest.severity]}>
          {group.latest.severity}
        </Badge>
        <span className="shrink-0 mt-0.5 text-text-muted" aria-hidden="true">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>

      {expanded && (
        <div className="ml-7 border-l border-surface-border pl-3 pb-1">
          {sorted.map((event) => (
            <div key={event.id} className="flex items-center gap-2 py-1.5 text-xs text-text-muted">
              <span className="font-mono">{formatDate(event.timestamp)}</span>
              <span className="text-text-secondary">{event.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function EventList({ events, isLoading, hasMore, onLoadMore }: EventListProps) {
  const groups = useMemo(() => groupEvents(events), [events]);

  if (!isLoading && events.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-text-muted">
        No events match your filters.
      </div>
    );
  }

  return (
    <div>
      <div className="divide-y divide-surface-border" role="list" aria-label="Event log">
        {groups.map((group) => (
          <GroupedEventRow key={`${group.key}-${group.latest.id}`} group={group} />
        ))}
      </div>

      {isLoading && (
        <div className="py-4 text-center text-sm text-text-muted">Loading...</div>
      )}

      {hasMore && !isLoading && (
        <div className="py-4 text-center">
          <button
            onClick={onLoadMore}
            className="text-sm text-accent-cyan hover:underline"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
