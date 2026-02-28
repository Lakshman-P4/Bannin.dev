'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { AnimatedPage } from '@/components/shared/AnimatedPage';
import { Card } from '@/components/ui/Card';
import { EventFilters } from '@/components/events/EventFilters';
import { EventList } from '@/components/events/EventList';
import { api } from '@/lib/api';
import type { AgentEvent } from '@/types';

const PAGE_SIZE = 20;

export default function EventsPage() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [type, setType] = useState('');
  const [severity, setSeverity] = useState('');
  const [since, setSince] = useState('24h');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce query changes into a stable debouncedQuery
  const handleSearchChange = useCallback((value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(value);
    }, 400);
  }, []);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const loadEvents = useCallback(
    async (offset = 0, append = false) => {
      setIsLoading(true);
      try {
        let res;
        if (debouncedQuery.trim()) {
          res = await api.events.search(debouncedQuery.trim(), PAGE_SIZE, offset);
        } else {
          res = await api.events.list({
            type: type || undefined,
            severity: severity || undefined,
            since: since || undefined,
            limit: PAGE_SIZE,
            offset,
          });
        }
        setEvents((prev) => (append ? [...prev, ...res.data] : res.data));
        setHasMore(res.meta.hasMore);
        setLoadError('');
      } catch (err) {
        console.error('Failed to load events:', err);
        if (!append) {
          setEvents([]);
          setLoadError('Failed to load events. Try again.');
        }
      } finally {
        setIsLoading(false);
      }
    },
    [debouncedQuery, type, severity, since],
  );

  // Single fetch trigger: fires when any filter or debouncedQuery changes
  useEffect(() => {
    loadEvents(0, false);
  }, [loadEvents]);

  const handleLoadMore = useCallback(() => {
    loadEvents(events.length, true);
  }, [loadEvents, events.length]);

  return (
    <AnimatedPage>
      <h1 className="font-display text-2xl font-bold text-text-primary mb-6">Events</h1>

      <Card className="mb-4">
        <div className="relative mb-4">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Search events..."
            value={query}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full rounded-lg border border-surface-border bg-surface-raised pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-cyan/40 focus:outline-none focus:ring-1 focus:ring-accent-cyan/20"
            aria-label="Search events"
          />
        </div>
        <EventFilters
          type={type}
          severity={severity}
          since={since}
          onTypeChange={setType}
          onSeverityChange={setSeverity}
          onSinceChange={setSince}
        />
      </Card>

      {loadError && (
        <div className="mb-4 rounded-lg border border-status-red/20 bg-status-red/5 p-3 text-sm text-status-red" role="alert">
          {loadError}
        </div>
      )}

      <Card>
        <EventList
          events={events}
          isLoading={isLoading}
          hasMore={hasMore}
          onLoadMore={handleLoadMore}
        />
      </Card>
    </AnimatedPage>
  );
}
