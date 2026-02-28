import type { IncomingMessage } from "node:http";
import type WebSocket from "ws";
import { URL } from "node:url";
import { prisma } from "../lib/prisma.js";
import { logger } from "../lib/logger.js";
import { agentMessageSchema, trainingStoppedSchema } from "../schemas/ws-messages.schema.js";
import { MAX_WS_MESSAGE_SIZE, WS_PING_INTERVAL_MS } from "../constants.js";
import { findAgentByApiKey } from "../services/agents.service.js";
import { persistSnapshot } from "../services/metrics.service.js";
import * as eventsService from "../services/events.service.js";
import * as alertsService from "../services/alerts.service.js";
import { sendNotification } from "../services/push.service.js";
import {
  registerAgent, unregisterAgent, updateAgentHeartbeat,
  getDashboardsForAgent, clearPendingTrainingStop,
} from "./registry.js";
import { mapAgentTypeToRelayType, broadcastToClients } from "./messages.js";
import type { AgentMessageType } from "../types/index.js";

export async function handleAgentConnection(ws: WebSocket, req: IncomingMessage): Promise<void> {
  const url = new URL(req.url ?? "", `http://${req.headers.host ?? "localhost"}`);
  const apiKey = url.searchParams.get("key");

  if (!apiKey) {
    ws.close(4001, "API key required");
    return;
  }

  const agent = await findAgentByApiKey(apiKey);
  if (!agent) {
    ws.close(4001, "Invalid API key");
    return;
  }

  const { id: agentId, userId, name: agentName } = agent;
  logger.info({ agentId, agentName }, "Agent connected via WebSocket");

  await prisma.agent.update({
    where: { id: agentId },
    data: { isOnline: true, lastSeen: new Date() },
  }).catch((err: unknown) => logger.warn({ err, agentId }, "Failed to mark agent online"));

  registerAgent(agentId, ws, userId, agentName);

  const dashboards = getDashboardsForAgent(agentId);
  broadcastToClients(dashboards, { type: "agent_status", agentId, status: "connected" });

  // Persist connect event so it appears in the Events page
  eventsService.createEvent({
    agentId,
    type: "agent_status",
    source: "relay",
    severity: "info",
    message: `Agent "${agentName}" connected`,
    data: { status: "connected" },
  }).catch((err: unknown) => logger.debug({ err, agentId }, "Failed to persist connect event"));

  let alive = true;
  const pingInterval = setInterval(() => {
    if (!alive) {
      ws.terminate();
      return;
    }
    alive = false;
    ws.ping();
  }, WS_PING_INTERVAL_MS);

  ws.on("pong", () => { alive = true; });

  ws.on("message", (raw: Buffer | ArrayBuffer | Buffer[]) => {
    const data = Buffer.isBuffer(raw) ? raw : Buffer.concat(Array.isArray(raw) ? raw : [Buffer.from(raw)]);
    if (data.length > MAX_WS_MESSAGE_SIZE) {
      logger.warn({ agentId, size: data.length }, "Agent message exceeds size limit");
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(data.toString("utf-8"));
    } catch {
      logger.warn({ agentId }, "Agent sent invalid JSON");
      return;
    }

    // Handle training stopped confirmations
    const stoppedResult = trainingStoppedSchema.safeParse(parsed);
    if (stoppedResult.success) {
      clearPendingTrainingStop(stoppedResult.data.taskId);
      broadcastToClients(getDashboardsForAgent(agentId), {
        type: "training_stopped",
        agentId,
        taskId: stoppedResult.data.taskId,
        status: stoppedResult.data.status,
      });
      return;
    }

    // Validate agent message
    const result = agentMessageSchema.safeParse(parsed);
    if (!result.success) {
      const msgType = typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>).type : "unknown";
      logger.warn({ agentId, msgType, errors: result.error.flatten().fieldErrors }, "Agent message failed schema validation -- dropping");

      // Forward unvalidated messages for non-critical types so dashboard still gets data
      if (
        typeof parsed === "object" && parsed !== null &&
        typeof (parsed as Record<string, unknown>).type === "string" &&
        typeof (parsed as Record<string, unknown>).timestamp === "string"
      ) {
        const raw = parsed as { type: string; timestamp: string; data?: Record<string, unknown> };
        if (["metrics", "training", "health", "oom_prediction", "processes"].includes(raw.type) && raw.data) {
          const relayType = mapAgentTypeToRelayType(raw.type as AgentMessageType);
          broadcastToClients(getDashboardsForAgent(agentId), {
            type: relayType,
            agentId,
            timestamp: raw.timestamp,
            data: raw.data,
          });
        }
      }
      return;
    }

    const msg = result.data;

    updateAgentHeartbeat(agentId);
    prisma.agent.update({
      where: { id: agentId },
      data: { lastSeen: new Date() },
    }).catch((err: unknown) => logger.debug({ err, agentId }, "Failed to update lastSeen"));

    void processAgentMessage(agentId, userId, msg);

    // Forward to subscribed dashboard clients (except heartbeats)
    if (msg.type !== "heartbeat") {
      const relayType = mapAgentTypeToRelayType(msg.type);
      broadcastToClients(getDashboardsForAgent(agentId), {
        type: relayType,
        agentId,
        timestamp: msg.timestamp,
        data: msg.data,
      });
    }
  });

  ws.on("close", () => {
    clearInterval(pingInterval);
    unregisterAgent(agentId);

    prisma.agent.update({
      where: { id: agentId },
      data: { isOnline: false },
    }).catch((err: unknown) => logger.warn({ err, agentId }, "Failed to mark agent offline"));

    broadcastToClients(getDashboardsForAgent(agentId), {
      type: "agent_status", agentId, status: "disconnected",
    });

    // Persist disconnect event
    eventsService.createEvent({
      agentId,
      type: "agent_status",
      source: "relay",
      severity: "warning",
      message: `Agent "${agentName}" disconnected`,
      data: { status: "disconnected" },
    }).catch((err: unknown) => logger.debug({ err, agentId }, "Failed to persist disconnect event"));

    sendNotification(userId, {
      title: "Bannin",
      body: `Lost connection to ${agentName}`,
      data: { agentId, type: "disconnect" },
    }).catch(() => {});

    logger.info({ agentId, agentName }, "Agent disconnected");
  });

  ws.on("error", (err) => {
    logger.warn({ err, agentId }, "Agent WebSocket error");
  });
}

async function processAgentMessage(agentId: string, userId: string, msg: { type: string; timestamp: string; data: Record<string, unknown> }): Promise<void> {
  try {
    switch (msg.type) {
      case "metrics": {
        const data = msg.data as unknown as {
          cpu: { percent: number };
          memory: { percent: number };
          disk: { percent: number };
          gpu?: Array<{ memory_percent: number; gpu_utilization_percent: number }> | null;
          network?: Record<string, unknown>;
        };
        await persistSnapshot(agentId, data);
        break;
      }
      case "processes": {
        // Store latest processes in the most recent metric snapshot
        const latestSnapshot = await prisma.metricSnapshot.findFirst({
          where: { agentId },
          orderBy: { timestamp: "desc" },
          select: { id: true },
        });
        if (latestSnapshot) {
          await prisma.metricSnapshot.update({
            where: { id: latestSnapshot.id },
            data: { processes: msg.data as object },
          });
        }
        break;
      }
      case "alert": {
        const data = msg.data as { id: string; severity: string; message: string; value: number; threshold: number | null };
        await alertsService.persistAlert({
          agentId,
          severity: data.severity,
          message: data.message,
          value: data.value,
          threshold: data.threshold,
        });
        await eventsService.createEvent({
          agentId,
          type: "alert",
          source: "agent",
          severity: data.severity,
          message: data.message,
          data: msg.data,
        });

        if (data.severity === "critical" || data.severity === "warning") {
          await sendNotification(userId, {
            title: "Bannin",
            body: data.message,
            data: { agentId, type: "alert" },
          });
        }
        break;
      }
      case "oom_prediction": {
        const ram = (msg.data as { ram?: { severity?: string; current_percent?: number; minutes_until_full?: number | null } }).ram;
        if (ram?.severity === "critical" || ram?.severity === "warning") {
          await eventsService.createEvent({
            agentId,
            type: "oom_prediction",
            source: "agent",
            severity: ram.severity,
            message: `OOM prediction: RAM at ${ram.current_percent}%, ~${ram.minutes_until_full ?? "?"}m until full`,
            data: msg.data,
          });
          const body = ram.severity === "critical"
            ? `Your training might crash -- memory at ${ram.current_percent}% and climbing`
            : `Memory usage is growing -- ${ram.current_percent}% used, might fill in ~${ram.minutes_until_full}m`;
          await sendNotification(userId, {
            title: "Bannin",
            body,
            data: { agentId, type: "oom" },
          });
        }
        break;
      }
      case "training": {
        const data = msg.data as { completed_tasks?: Array<{ name?: string; elapsed_seconds?: number }>; stalled_tasks?: Array<{ name?: string }> };
        for (const task of data.completed_tasks ?? []) {
          const duration = formatDuration(task.elapsed_seconds ?? 0);
          await eventsService.createEvent({
            agentId,
            type: "training",
            source: "agent",
            severity: "info",
            message: `Training complete: ${task.name ?? "task"} finished in ${duration}`,
            data: task,
          });
          await sendNotification(userId, {
            title: "Bannin",
            body: `Training complete! ${task.name ?? "Task"} finished in ${duration}.`,
            data: { agentId, type: "training_complete" },
          });
        }
        for (const task of data.stalled_tasks ?? []) {
          await eventsService.createEvent({
            agentId,
            type: "training",
            source: "agent",
            severity: "warning",
            message: `Training stalled: ${task.name ?? "task"}`,
            data: task,
          });
        }
        break;
      }
      case "event": {
        const data = msg.data as { type: string; source: string; severity: string | null; message: string };
        await eventsService.createEvent({
          agentId,
          type: data.type,
          source: data.source,
          severity: data.severity,
          message: data.message,
          data: msg.data,
        });
        break;
      }
      // health, heartbeat -- forwarded to dashboard only, no persistence needed
    }
  } catch (err) {
    logger.warn({ err, agentId, type: msg.type }, "Failed to process agent message");
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}
