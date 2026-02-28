'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Server, Plus, ChevronRight } from 'lucide-react';
import { AnimatedPage } from '@/components/shared/AnimatedPage';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { BanninEye } from '@/components/shared/BanninEye';
import { useDashboardStore } from '@/stores/dashboardStore';
import { api } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import type { Agent } from '@/types';
import Link from 'next/link';

export default function HomePage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const setCurrentAgent = useDashboardStore((s) => s.setCurrentAgent);
  const router = useRouter();

  const loadAgents = useCallback(async () => {
    try {
      const res = await api.agents.list();
      setAgents(res.data);
    } catch {
      setLoadError('Failed to load agents. Check your connection and try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const handleSelectAgent = useCallback(
    (agent: Agent) => {
      setCurrentAgent(agent);
      router.push('/dashboard');
    },
    [setCurrentAgent, router],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div
          className="h-6 w-6 animate-spin rounded-full border-2 border-accent-cyan border-t-transparent"
          role="status"
          aria-label="Loading agents"
        />
      </div>
    );
  }

  if (loadError) {
    return (
      <AnimatedPage className="flex flex-col items-center justify-center py-24 text-center">
        <h1 className="font-display text-xl font-bold text-status-red mb-2">
          Something went wrong
        </h1>
        <p className="text-sm text-text-secondary mb-4">{loadError}</p>
        <Button onClick={() => { setLoadError(''); setIsLoading(true); loadAgents(); }}>
          Try again
        </Button>
      </AnimatedPage>
    );
  }

  if (agents.length === 0) {
    return (
      <AnimatedPage className="flex flex-col items-center justify-center py-24 text-center">
        <BanninEye size={64} />
        <h1 className="font-display text-2xl font-bold text-text-primary mt-6 mb-2">
          Welcome to Bannin
        </h1>
        <p className="text-sm text-text-secondary mb-6 max-w-md">
          Connect your first agent to start monitoring. It takes 2 minutes.
        </p>
        <Link href="/setup">
          <Button>Set up your first agent</Button>
        </Link>
      </AnimatedPage>
    );
  }

  return (
    <AnimatedPage>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-text-primary">
            Your Agents
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {agents.length} agent{agents.length !== 1 ? 's' : ''} registered
          </p>
        </div>
        <Link href="/setup">
          <Button variant="secondary" size="sm">
            <Plus size={16} aria-hidden="true" className="mr-1.5" />
            Add Agent
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => (
          <button
            key={agent.id}
            onClick={() => handleSelectAgent(agent)}
            className="group text-left w-full"
            aria-label={`Open dashboard for ${agent.name}`}
          >
            <Card hoverable className="h-full transition-colors group-hover:border-accent-cyan/30">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-raised">
                    <Server size={18} className="text-text-muted" aria-hidden="true" />
                  </div>
                  <div>
                    <h2 className="font-display text-sm font-semibold text-text-primary">
                      {agent.name}
                    </h2>
                    {agent.hostname && (
                      <p className="text-xs text-text-muted">{agent.hostname}</p>
                    )}
                  </div>
                </div>
                <Badge variant={agent.isOnline ? 'success' : 'default'}>
                  {agent.isOnline ? 'Online' : 'Offline'}
                </Badge>
              </div>

              <div className="space-y-1.5 text-xs text-text-muted">
                {agent.os && (
                  <p>
                    <span className="text-text-secondary">OS:</span> {agent.os}
                  </p>
                )}
                {agent.agentVersion && (
                  <p>
                    <span className="text-text-secondary">Version:</span> v{agent.agentVersion}
                  </p>
                )}
                <p>
                  <span className="text-text-secondary">Last seen:</span>{' '}
                  {formatRelativeTime(agent.lastSeen)}
                </p>
              </div>

              <div className="mt-3 flex items-center justify-end text-xs text-text-muted group-hover:text-accent-cyan transition-colors">
                <span>Open dashboard</span>
                <ChevronRight size={14} aria-hidden="true" className="ml-0.5" />
              </div>
            </Card>
          </button>
        ))}
      </div>
    </AnimatedPage>
  );
}
