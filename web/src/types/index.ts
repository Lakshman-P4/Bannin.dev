export interface User {
  id: string;
  username: string;
  displayName: string;
  email: string | null;
  emailVerified: boolean;
  createdAt: string;
}

export interface AuthResponse {
  data: {
    user: User;
    accessToken: string;
    refreshToken: string;
  };
}

export interface Agent {
  id: string;
  name: string;
  hostname: string;
  os: string;
  agentVersion: string;
  isOnline: boolean;
  lastSeen: string;
  createdAt: string;
}

export interface AgentWithKey extends Agent {
  apiKey: string;
}

export interface MetricSnapshot {
  id: string;
  timestamp: string;
  cpu: number;
  memory: number;
  disk: number;
  gpu: number | null;
  gpuMemory: number | null;
  network: NetworkData | null;
  processes: ProcessData | null;
}

export interface NetworkData {
  bytesSent: number;
  bytesRecv: number;
}

export interface ProcessData {
  top: ProcessInfo[];
}

export interface ProcessInfo {
  name: string;
  category: string;
  cpuPercent: number;
  memoryMb: number;
  instanceCount: number;
}

export interface OOMPrediction {
  ram: OOMDetail;
  gpu: OOMDetail[];
}

export interface OOMDetail {
  confidence: number;
  minutesUntilFull: number | null;
  severity: 'ok' | 'warning' | 'critical';
  currentPercent: number;
  growthRatePctPerMin: number;
}

export interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  value: number | null;
  threshold: number | null;
  firedAt: string;
  resolvedAt: string | null;
  acknowledged: boolean;
}

export interface TrainingTask {
  id: string;
  name: string;
  source: string;
  current: number;
  total: number | null;
  percentComplete: number;
  elapsedSeconds: number;
  etaSeconds: number | null;
  etaHuman: string | null;
  startedAt: string | null;
  status: 'running' | 'completed' | 'stalled';
}

export interface DetectedTask {
  pid: number;
  name: string;
  via: string;
  cpuPercent: number;
  memoryPercent: number;
  elapsedSeconds: number;
  elapsedHuman: string;
  status: 'running' | 'finished';
}

export interface TrainingStatus {
  activeTasks: TrainingTask[];
  completedTasks: TrainingTask[];
  stalledTasks: TrainingTask[];
  detectedTasks: DetectedTask[];
  totalTracked: number;
}

export interface AgentEvent {
  id: string;
  type: string;
  source: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    total: number;
    limit: number;
    offset: number;
    hasMore: boolean;
  };
}

export interface EventFilters {
  type?: string;
  severity?: string;
  since?: string;
  limit?: number;
  offset?: number;
}

export interface TimelineFilters extends EventFilters {
  agentId?: string;
}

export interface DashboardOverview {
  agent: Agent;
  metrics: MetricSnapshot | null;
  alerts: Alert[];
  oomPrediction: OOMPrediction | null;
  training: TrainingStatus | null;
  recentEvents: AgentEvent[];
}

export interface HealthComponent {
  score: number;
  weight: number;
  detail: string;
}

export interface ConversationHealth {
  healthScore: number;
  rating: string;
  source: string;
  components: Record<string, HealthComponent>;
  recommendation: string | null;
}

export type UrgencyLevel = 'normal' | 'warning' | 'critical';

/** Raw WebSocket messages from the relay server (agent data in snake_case). */
export type WebSocketMessage =
  | { type: 'agent_metrics'; agentId: string; data: Record<string, unknown>; timestamp: string }
  | { type: 'agent_alert'; agentId: string; data: Record<string, unknown>; timestamp: string }
  | { type: 'agent_oom'; agentId: string; data: Record<string, unknown>; timestamp: string }
  | { type: 'agent_training'; agentId: string; data: Record<string, unknown>; timestamp: string }
  | { type: 'agent_event'; agentId: string; data: Record<string, unknown>; timestamp: string }
  | { type: 'agent_processes'; agentId: string; data: Record<string, unknown>; timestamp: string }
  | { type: 'agent_health'; agentId: string; data: Record<string, unknown>; timestamp: string }
  | { type: 'agent_status'; agentId: string; status: 'connected' | 'disconnected' }
  | { type: 'training_stopped'; agentId: string; taskId: string; status: 'graceful' | 'forced' }
  | { type: 'error'; message: string };
