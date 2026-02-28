import type WebSocket from "ws";
import type { AgentMessageType, RelayToDashboardType } from "../types/index.js";

const TYPE_MAP: Record<AgentMessageType, RelayToDashboardType> = {
  metrics: "agent_metrics",
  alert: "agent_alert",
  oom_prediction: "agent_oom",
  training: "agent_training",
  event: "agent_event",
  processes: "agent_processes",
  health: "agent_health",
  heartbeat: "agent_metrics", // heartbeats don't get forwarded; this is a fallback
};

export function mapAgentTypeToRelayType(agentType: AgentMessageType): RelayToDashboardType {
  return TYPE_MAP[agentType] ?? "agent_event";
}

export function sendToClient(ws: WebSocket, message: Record<string, unknown>): void {
  if (ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

export function broadcastToClients(clients: WebSocket[], message: Record<string, unknown>): void {
  const payload = JSON.stringify(message);
  for (const ws of clients) {
    if (ws.readyState === ws.OPEN) {
      ws.send(payload);
    }
  }
}
