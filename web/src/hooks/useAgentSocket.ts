'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useDashboardStore } from '@/stores/dashboardStore';
import { getAccessToken, waitForTokenRefresh, refreshAccessToken } from '@/lib/api';
import type {
  WebSocketMessage,
  MetricSnapshot,
  Alert,
  OOMPrediction,
  OOMDetail,
  TrainingStatus,
  TrainingTask,
  DetectedTask,
  AgentEvent,
  ConversationHealth,
  HealthComponent,
} from '@/types';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:3001';
const MAX_RECONNECT_DELAY = 30_000;
const BASE_RECONNECT_DELAY = 1_000;

/** Grace period before showing "Disconnected" to absorb brief reconnects. */
const DISCONNECT_GRACE_MS = 3_000;

/** Close code sent by relay when JWT is invalid or expired. */
const WS_CLOSE_AUTH_FAILED = 4001;

// ---------------------------------------------------------------------------
// Raw -> Frontend type transformers (snake_case -> camelCase)
// ---------------------------------------------------------------------------

/* eslint-disable @typescript-eslint/no-explicit-any */

function transformMetrics(raw: any, timestamp: string): MetricSnapshot {
  const gpu0 = Array.isArray(raw.gpu) && raw.gpu.length > 0 ? raw.gpu[0] : null;
  return {
    id: '',
    timestamp,
    cpu: raw.cpu?.percent ?? 0,
    memory: raw.memory?.percent ?? 0,
    disk: raw.disk?.percent ?? 0,
    gpu: gpu0?.gpu_utilization_percent ?? null,
    gpuMemory: gpu0?.memory_percent ?? null,
    network: raw.network
      ? { bytesSent: raw.network.bytes_sent ?? 0, bytesRecv: raw.network.bytes_received ?? 0 }
      : null,
    processes: null,
  };
}

function transformAlert(raw: any): Alert {
  return {
    id: raw.id ?? '',
    severity: raw.severity ?? 'info',
    message: raw.message ?? '',
    value: raw.value ?? null,
    threshold: raw.threshold ?? null,
    firedAt: raw.fired_at ?? new Date().toISOString(),
    resolvedAt: null,
    acknowledged: false,
  };
}

function transformOOM(raw: any): OOMPrediction {
  const normalizeSeverity = (s: string | undefined): 'ok' | 'warning' | 'critical' => {
    if (s === 'critical') return 'critical';
    if (s === 'warning') return 'warning';
    return 'ok'; // 'ok', 'info', 'low_confidence', undefined -> 'ok'
  };

  const mapDetail = (d: any): OOMDetail => ({
    confidence: d?.confidence ?? 0,
    minutesUntilFull: d?.minutes_until_full ?? null,
    severity: normalizeSeverity(d?.severity),
    currentPercent: d?.current_percent ?? d?.current_percent ?? 0,
    growthRatePctPerMin: d?.growth_rate_per_min ?? 0,
  });

  return {
    ram: mapDetail(raw.ram),
    gpu: Array.isArray(raw.gpu) ? raw.gpu.map(mapDetail) : [],
  };
}

function transformTraining(raw: any): TrainingStatus {
  const mapTask = (t: any): TrainingTask => ({
    id: t?.task_id ?? t?.id ?? t?.name ?? '',
    name: t?.name ?? '',
    source: t?.source ?? 'unknown',
    current: Number(t?.current) || 0,
    total: t?.total != null ? Number(t.total) : null,
    percentComplete: t?.percent_complete ?? t?.percent ?? 0,
    elapsedSeconds: t?.elapsed_seconds ?? 0,
    etaSeconds: t?.eta_seconds ?? null,
    etaHuman: t?.eta_human ?? null,
    startedAt: t?.started_at ?? null,
    status: t?.status ?? 'running',
  });

  const mapDetected = (d: any): DetectedTask => ({
    pid: Number(d?.pid) || 0,
    name: d?.name ?? '',
    via: d?.via ?? 'unknown',
    cpuPercent: Number(d?.cpu_percent) || 0,
    memoryPercent: Number(d?.memory_percent) || 0,
    elapsedSeconds: Number(d?.elapsed_seconds) || 0,
    elapsedHuman: d?.elapsed_human ?? '0s',
    status: d?.status === 'finished' ? 'finished' : 'running',
  });

  return {
    activeTasks: Array.isArray(raw.active_tasks) ? raw.active_tasks.map(mapTask) : [],
    completedTasks: Array.isArray(raw.completed_tasks) ? raw.completed_tasks.map(mapTask) : [],
    stalledTasks: Array.isArray(raw.stalled_tasks) ? raw.stalled_tasks.map(mapTask) : [],
    detectedTasks: Array.isArray(raw.detected_tasks) ? raw.detected_tasks.map(mapDetected) : [],
    totalTracked: Number(raw.total_tracked) || 0,
  };
}

function transformEvent(raw: any, timestamp: string): AgentEvent {
  return {
    id: raw.id ?? '',
    type: raw.type ?? 'unknown',
    source: raw.source ?? 'agent',
    severity: raw.severity ?? 'info',
    message: raw.message ?? '',
    data: raw.data ?? null,
    timestamp: raw.timestamp ?? timestamp,
  };
}

function transformHealth(raw: any): ConversationHealth {
  const components: Record<string, HealthComponent> = {};
  const rawComponents = raw.components ?? {};
  for (const key of Object.keys(rawComponents)) {
    const c = rawComponents[key];
    components[key] = {
      score: Number(c?.score) || 0,
      weight: Number(c?.weight) || 0,
      detail: String(c?.detail ?? ''),
    };
  }
  return {
    healthScore: Number(raw.health_score) || 0,
    rating: String(raw.rating ?? 'unknown'),
    source: String(raw.source ?? ''),
    components,
    recommendation: raw.recommendation ?? null,
  };
}

/* eslint-enable @typescript-eslint/no-explicit-any */

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface AgentSocketActions {
  sendMessage: (message: Record<string, unknown>) => void;
}

export function useAgentSocket(agentId: string | null): AgentSocketActions {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disconnectGraceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const mountedRef = useRef(true);
  const agentIdRef = useRef(agentId);
  agentIdRef.current = agentId;

  // Store actions via ref so handleMessage never changes identity
  const storeRef = useRef(useDashboardStore.getState());
  useEffect(() => {
    return useDashboardStore.subscribe((state) => {
      storeRef.current = state;
    });
  }, []);

  const setConnectedDebounced = useCallback((connected: boolean) => {
    // Clear any pending grace timer
    if (disconnectGraceRef.current) {
      clearTimeout(disconnectGraceRef.current);
      disconnectGraceRef.current = null;
    }

    if (connected) {
      // Connected: update immediately
      storeRef.current.setConnected(true);
    } else {
      // Disconnected: wait grace period before showing to user
      disconnectGraceRef.current = setTimeout(() => {
        if (mountedRef.current) {
          storeRef.current.setConnected(false);
        }
      }, DISCONNECT_GRACE_MS);
    }
  }, []);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      let msg: WebSocketMessage;
      try {
        msg = JSON.parse(String(event.data)) as WebSocketMessage;
      } catch {
        return;
      }

      const currentAgentId = agentIdRef.current;
      if ('agentId' in msg && msg.agentId !== currentAgentId) return;

      const store = storeRef.current;

      switch (msg.type) {
        case 'agent_metrics':
          store.setMetrics(transformMetrics(msg.data, msg.timestamp));
          break;
        case 'agent_alert':
          store.addAlert(transformAlert(msg.data));
          break;
        case 'agent_oom':
          store.setOOMPrediction(transformOOM(msg.data));
          break;
        case 'agent_training':
          store.setTraining(transformTraining(msg.data));
          break;
        case 'agent_health':
          store.setConversationHealth(transformHealth(msg.data));
          break;
        case 'agent_event':
          store.addEvent(transformEvent(msg.data, msg.timestamp));
          break;
        case 'agent_status':
          store.setAgentOnline(msg.status === 'connected');
          break;
        case 'training_stopped':
          // Handled by the dashboard page via toast
          break;
      }
    },
    [], // Stable: reads agentId and store from refs
  );

  const sendMessage = useCallback(
    (message: Record<string, unknown>) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(message));
      }
    },
    [],
  );

  const connect = useCallback(async () => {
    const currentAgentId = agentIdRef.current;
    if (!currentAgentId || !mountedRef.current) return;

    // Wait for any in-flight token refresh before reading the token
    await waitForTokenRefresh();
    if (!mountedRef.current) return;

    const token = getAccessToken();
    if (!token) return;

    if (wsRef.current) {
      wsRef.current.close();
    }

    // Relay server authenticates via query parameter on upgrade
    const ws = new WebSocket(
      `${WS_URL}/ws/dashboard?token=${encodeURIComponent(token)}`,
    );
    wsRef.current = ws;

    ws.addEventListener('open', () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      reconnectAttemptRef.current = 0;
      setConnectedDebounced(true);
      ws.send(JSON.stringify({ type: 'subscribe', agentId: agentIdRef.current }));
    });

    ws.addEventListener('message', handleMessage);

    ws.addEventListener('close', (closeEvent) => {
      if (!mountedRef.current) return;
      setConnectedDebounced(false);

      // If closed due to auth failure, refresh the token before reconnecting
      if (closeEvent.code === WS_CLOSE_AUTH_FAILED) {
        void (async () => {
          const refreshed = await refreshAccessToken();
          if (!mountedRef.current) return;
          if (refreshed) {
            reconnectAttemptRef.current = 0;
            reconnectTimeoutRef.current = setTimeout(() => {
              if (mountedRef.current) void connect();
            }, 500);
          } else {
            scheduleReconnect();
          }
        })();
        return;
      }

      scheduleReconnect();
    });

    ws.addEventListener('error', () => {
      ws.close();
    });

    function scheduleReconnect(): void {
      const delay = Math.min(
        BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptRef.current),
        MAX_RECONNECT_DELAY,
      );
      reconnectAttemptRef.current += 1;

      reconnectTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) void connect();
      }, delay);
    }
  }, [handleMessage, setConnectedDebounced]); // Stable: both deps are stable

  useEffect(() => {
    mountedRef.current = true;
    void connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (disconnectGraceRef.current) {
        clearTimeout(disconnectGraceRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { sendMessage };
}
