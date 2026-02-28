'use client';

import { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Cpu, MemoryStick, HardDrive, Monitor } from 'lucide-react';
import { AnimatedPage } from '@/components/shared/AnimatedPage';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { OOMCard } from '@/components/dashboard/OOMCard';
import { AlertList } from '@/components/dashboard/AlertList';
import { TrainingProgress } from '@/components/dashboard/TrainingProgress';
import { MemoryChart } from '@/components/dashboard/MemoryChart';
import { EventFeed } from '@/components/dashboard/EventFeed';
import { ConversationHealth } from '@/components/dashboard/ConversationHealth';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useDashboardStore } from '@/stores/dashboardStore';
import { useAgentSocket } from '@/hooks/useAgentSocket';
import { api } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import type { Agent } from '@/types';
import Link from 'next/link';

export default function DashboardPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const {
    currentAgent,
    metrics,
    metricsHistory,
    alerts,
    oomPrediction,
    training,
    conversationHealth,
    recentEvents,
    trainingNotifications,
    setCurrentAgent,
    clearTrainingNotifications,
  } = useDashboardStore();

  const { sendMessage } = useAgentSocket(currentAgent?.id ?? null);

  // Surface training state transitions as toasts
  useEffect(() => {
    if (trainingNotifications.length === 0) return;

    for (const notification of trainingNotifications) {
      if (notification.event === 'completed') {
        toast.success(`Training complete: ${notification.taskName}`, { duration: 5000 });
      } else if (notification.event === 'stalled') {
        toast.warning(`Training stalled: ${notification.taskName}`, { duration: 7000 });
      }
    }

    clearTrainingNotifications();
  }, [trainingNotifications, clearTrainingNotifications]);

  const handleStopTask = useCallback(
    (taskId: string) => {
      if (!currentAgent) return;
      sendMessage({ type: 'training_stop', agentId: currentAgent.id, taskId });
      toast.info('Stop signal sent. Waiting for graceful shutdown...', { duration: 4000 });
    },
    [currentAgent, sendMessage],
  );

  const loadAgents = useCallback(async () => {
    try {
      const res = await api.agents.list();
      setAgents(res.data);
      // Only auto-select if no agent is currently selected (checked via store snapshot)
      if (res.data.length > 0) {
        const current = useDashboardStore.getState().currentAgent;
        if (!current) {
          setCurrentAgent(res.data[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load agents:', err);
      setLoadError('Failed to load agents. Check your connection and try again.');
    } finally {
      setIsLoading(false);
    }
  }, [setCurrentAgent]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div
          className="h-6 w-6 animate-spin rounded-full border-2 border-accent-cyan border-t-transparent"
          role="status"
          aria-label="Loading dashboard"
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
        <h1 className="font-display text-2xl font-bold text-text-primary mb-2">
          No agent connected
        </h1>
        <p className="text-sm text-text-secondary mb-6 max-w-md">
          Let&apos;s fix that -- it takes 2 minutes. Install the agent on the machine
          you want to monitor and connect it to your account.
        </p>
        <Link href="/setup">
          <Button>Set up your first agent</Button>
        </Link>
      </AnimatedPage>
    );
  }

  return (
    <AnimatedPage>
      {currentAgent && (
        <div className="mb-6 flex items-center gap-3">
          <h1 className="font-display text-xl font-bold text-text-primary">
            {currentAgent.name}
          </h1>
          <Badge variant={currentAgent.isOnline ? 'success' : 'default'}>
            {currentAgent.isOnline ? 'Online' : 'Offline'}
          </Badge>
          <span className="text-xs text-text-muted">
            Last seen: {formatRelativeTime(currentAgent.lastSeen)}
          </span>
        </div>
      )}

      {currentAgent && !currentAgent.isOnline && (
        <div className="glass-card mb-6 p-4">
          <p className="text-sm text-text-secondary">
            Your agent is offline. Start it with:{' '}
            <code className="font-mono text-accent-cyan">bannin start --relay YOUR_KEY</code>
          </p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="CPU"
          value={metrics?.cpu ?? null}
          icon={<Cpu size={18} />}
        />
        <MetricCard
          label="Memory"
          value={metrics?.memory ?? null}
          icon={<MemoryStick size={18} />}
        />
        <MetricCard
          label="Disk"
          value={metrics?.disk ?? null}
          icon={<HardDrive size={18} />}
        />
        <MetricCard
          label="GPU"
          value={metrics?.gpu ?? null}
          icon={<Monitor size={18} />}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <OOMCard prediction={oomPrediction} />
        <AlertList alerts={alerts} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <ConversationHealth health={conversationHealth} />
        <TrainingProgress training={training} onStopTask={handleStopTask} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <MemoryChart history={metricsHistory} />
      </div>

      <div className="mt-6">
        <EventFeed events={recentEvents} />
      </div>
    </AnimatedPage>
  );
}
