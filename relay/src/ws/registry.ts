import type WebSocket from "ws";

interface AgentConnection {
  ws: WebSocket;
  agentId: string;
  userId: string;
  agentName: string;
  lastHeartbeat: number;
}

interface DashboardConnection {
  ws: WebSocket;
  userId: string;
  subscribedAgents: Set<string>;
}

// In-memory connection registries (per-instance)
const agentConnections = new Map<string, AgentConnection>();
const dashboardConnections = new Map<WebSocket, DashboardConnection>();

// Pending training stops: taskId -> timeout handle
const pendingTrainingStops = new Map<string, ReturnType<typeof setTimeout>>();

export function registerAgent(agentId: string, ws: WebSocket, userId: string, agentName: string): void {
  agentConnections.set(agentId, { ws, agentId, userId, agentName, lastHeartbeat: Date.now() });
}

export function unregisterAgent(agentId: string): void {
  agentConnections.delete(agentId);
}

export function getAgentConnection(agentId: string): AgentConnection | undefined {
  return agentConnections.get(agentId);
}

export function updateAgentHeartbeat(agentId: string): void {
  const conn = agentConnections.get(agentId);
  if (conn) {
    conn.lastHeartbeat = Date.now();
  }
}

export function getConnectedAgentCount(): number {
  return agentConnections.size;
}

export function getAllAgentConnections(): Map<string, AgentConnection> {
  return agentConnections;
}

export function registerDashboard(ws: WebSocket, userId: string): void {
  dashboardConnections.set(ws, { ws, userId, subscribedAgents: new Set() });
}

export function unregisterDashboard(ws: WebSocket): void {
  dashboardConnections.delete(ws);
}

export function subscribeDashboardToAgent(ws: WebSocket, agentId: string): void {
  const conn = dashboardConnections.get(ws);
  if (conn) {
    conn.subscribedAgents.add(agentId);
  }
}

export function unsubscribeDashboardFromAgent(ws: WebSocket, agentId: string): void {
  const conn = dashboardConnections.get(ws);
  if (conn) {
    conn.subscribedAgents.delete(agentId);
  }
}

export function getDashboardsForAgent(agentId: string): WebSocket[] {
  const result: WebSocket[] = [];
  for (const conn of dashboardConnections.values()) {
    if (conn.subscribedAgents.has(agentId)) {
      result.push(conn.ws);
    }
  }
  return result;
}

export function getAgentOwnerUserId(agentId: string): string | undefined {
  return agentConnections.get(agentId)?.userId;
}

export function setPendingTrainingStop(taskId: string, timeout: ReturnType<typeof setTimeout>): void {
  pendingTrainingStops.set(taskId, timeout);
}

export function clearPendingTrainingStop(taskId: string): void {
  const timeout = pendingTrainingStops.get(taskId);
  if (timeout) {
    clearTimeout(timeout);
    pendingTrainingStops.delete(taskId);
  }
}
