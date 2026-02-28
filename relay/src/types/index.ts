export interface JwtPayload {
  id: string;
  username: string;
  email: string | null;
  emailVerified: boolean;
}

export interface AuthenticatedUser {
  id: string;
  username: string;
  email: string | null;
  emailVerified: boolean;
}

export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface SuccessResponse<T> {
  data: T;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginationMeta;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
  };
}

export type AgentMessageType =
  | "metrics"
  | "alert"
  | "oom_prediction"
  | "training"
  | "event"
  | "processes"
  | "health"
  | "heartbeat";

export type DashboardMessageType =
  | "subscribe"
  | "unsubscribe"
  | "training_stop";

export type RelayToDashboardType =
  | "agent_metrics"
  | "agent_alert"
  | "agent_oom"
  | "agent_training"
  | "agent_event"
  | "agent_processes"
  | "agent_health"
  | "agent_status";
