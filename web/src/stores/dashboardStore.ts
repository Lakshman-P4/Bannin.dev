import { create } from 'zustand';
import type {
  Agent,
  MetricSnapshot,
  Alert,
  OOMPrediction,
  TrainingStatus,
  AgentEvent,
  ConversationHealth,
} from '@/types';

const MAX_EVENTS = 50;
const MAX_METRIC_HISTORY = 60;
const MAX_TRAINING_NOTIFICATIONS = 20;

export interface TrainingNotification {
  taskId: string;
  taskName: string;
  event: 'completed' | 'stalled';
  timestamp: number;
}

interface DashboardState {
  currentAgent: Agent | null;
  metrics: MetricSnapshot | null;
  metricsHistory: MetricSnapshot[];
  alerts: Alert[];
  oomPrediction: OOMPrediction | null;
  training: TrainingStatus | null;
  trainingNotifications: TrainingNotification[];
  conversationHealth: ConversationHealth | null;
  recentEvents: AgentEvent[];
  isConnected: boolean;

  setCurrentAgent: (agent: Agent | null) => void;
  setMetrics: (metrics: MetricSnapshot) => void;
  setAlerts: (alerts: Alert[]) => void;
  addAlert: (alert: Alert) => void;
  dismissAlert: (id: string) => void;
  setOOMPrediction: (prediction: OOMPrediction | null) => void;
  setTraining: (training: TrainingStatus | null) => void;
  setConversationHealth: (health: ConversationHealth | null) => void;
  addEvent: (event: AgentEvent) => void;
  setRecentEvents: (events: AgentEvent[]) => void;
  setAgentOnline: (isOnline: boolean) => void;
  setConnected: (connected: boolean) => void;
  clearTrainingNotifications: () => void;
  reset: () => void;
}

const initialState = {
  currentAgent: null,
  metrics: null,
  metricsHistory: [],
  alerts: [],
  oomPrediction: null,
  training: null,
  trainingNotifications: [] as TrainingNotification[],
  conversationHealth: null,
  recentEvents: [],
  isConnected: false,
};

export const useDashboardStore = create<DashboardState>((set) => ({
  ...initialState,

  setCurrentAgent: (agent) => set({ currentAgent: agent }),

  setMetrics: (metrics) =>
    set((state) => ({
      metrics,
      metricsHistory: [...state.metricsHistory, metrics].slice(-MAX_METRIC_HISTORY),
    })),

  setAlerts: (alerts) => set({ alerts }),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, MAX_EVENTS),
    })),

  dismissAlert: (id) =>
    set((state) => ({
      alerts: state.alerts.filter((a) => a.id !== id),
    })),

  setOOMPrediction: (prediction) => set({ oomPrediction: prediction }),

  setTraining: (training) =>
    set((state) => {
      const notifications: TrainingNotification[] = [];
      const now = Date.now();

      if (state.training && training) {
        const prevActiveIds = new Set(state.training.activeTasks.map((t) => t.id));

        for (const task of training.completedTasks) {
          if (prevActiveIds.has(task.id)) {
            notifications.push({
              taskId: task.id,
              taskName: task.name,
              event: 'completed',
              timestamp: now,
            });
          }
        }

        for (const task of training.stalledTasks) {
          if (prevActiveIds.has(task.id)) {
            notifications.push({
              taskId: task.id,
              taskName: task.name,
              event: 'stalled',
              timestamp: now,
            });
          }
        }
      }

      return {
        training,
        trainingNotifications: [...notifications, ...state.trainingNotifications].slice(
          0,
          MAX_TRAINING_NOTIFICATIONS,
        ),
      };
    }),

  setConversationHealth: (health) => set({ conversationHealth: health }),

  addEvent: (event) =>
    set((state) => ({
      recentEvents: [event, ...state.recentEvents].slice(0, MAX_EVENTS),
    })),

  setRecentEvents: (events) => set({ recentEvents: events.slice(0, MAX_EVENTS) }),

  setAgentOnline: (isOnline) =>
    set((state) => ({
      currentAgent: state.currentAgent
        ? { ...state.currentAgent, isOnline }
        : null,
    })),

  setConnected: (connected) => set({ isConnected: connected }),

  clearTrainingNotifications: () => set({ trainingNotifications: [] }),

  reset: () => set(initialState),
}));
