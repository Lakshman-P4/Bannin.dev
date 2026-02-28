import type { IncomingMessage } from "node:http";
import type WebSocket from "ws";
import { URL } from "node:url";
import jwt from "jsonwebtoken";
import { getEnv } from "../config/env.js";
import { logger } from "../lib/logger.js";
import { prisma } from "../lib/prisma.js";
import { dashboardMessageSchema, type DashboardMessage } from "../schemas/ws-messages.schema.js";
import { WS_PING_INTERVAL_MS, MAX_WS_MESSAGE_SIZE, TRAINING_STOP_GRACE_MS } from "../constants.js";
import type { JwtPayload } from "../types/index.js";
import {
  registerDashboard, unregisterDashboard,
  subscribeDashboardToAgent, unsubscribeDashboardFromAgent,
  getAgentConnection, setPendingTrainingStop, clearPendingTrainingStop,
} from "./registry.js";
import { sendToClient } from "./messages.js";
import { getLatestSnapshot } from "../services/metrics.service.js";

export async function handleDashboardConnection(ws: WebSocket, req: IncomingMessage): Promise<void> {
  const url = new URL(req.url ?? "", `http://${req.headers.host ?? "localhost"}`);
  const token = url.searchParams.get("token");

  if (!token) {
    ws.close(4001, "JWT token required");
    return;
  }

  let user: JwtPayload;
  try {
    const env = getEnv();
    user = jwt.verify(token, env.JWT_SECRET) as JwtPayload;
  } catch {
    ws.close(4001, "Invalid or expired token");
    return;
  }

  logger.info({ userId: user.id }, "Dashboard client connected");
  registerDashboard(ws, user.id);

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
    if (data.length > MAX_WS_MESSAGE_SIZE) return;

    let parsed: unknown;
    try {
      parsed = JSON.parse(data.toString("utf-8"));
    } catch {
      return;
    }

    const result = dashboardMessageSchema.safeParse(parsed);
    if (!result.success) {
      sendToClient(ws, { type: "error", message: "Invalid message format" });
      return;
    }

    const msg = result.data;
    void handleDashboardMessage(ws, user, msg);
  });

  ws.on("close", () => {
    clearInterval(pingInterval);
    unregisterDashboard(ws);
    logger.info({ userId: user.id }, "Dashboard client disconnected");
  });

  ws.on("error", (err) => {
    logger.warn({ err, userId: user.id }, "Dashboard WebSocket error");
  });
}

async function handleDashboardMessage(ws: WebSocket, user: JwtPayload, msg: DashboardMessage): Promise<void> {
  switch (msg.type) {
    case "subscribe": {
      const agent = await prisma.agent.findFirst({
        where: { id: msg.agentId, userId: user.id },
        select: { id: true, isOnline: true },
      });
      if (!agent) {
        sendToClient(ws, { type: "error", message: "Agent not found" });
        return;
      }
      subscribeDashboardToAgent(ws, msg.agentId);
      sendToClient(ws, {
        type: "agent_status",
        agentId: msg.agentId,
        status: agent.isOnline ? "connected" : "disconnected",
      });

      // Backfill latest metrics so the dashboard doesn't show "--" until the
      // next agent push cycle (up to 5 seconds away).
      const latest = await getLatestSnapshot(msg.agentId) as {
        timestamp: Date; cpu: number; memory: number; disk: number;
        gpu: number | null; gpuMemory: number | null;
        network: unknown; raw: unknown;
      } | null;
      if (latest) {
        // Prefer the raw JSON (full nested structure) if available,
        // otherwise reconstruct from flattened columns.
        const rawData = latest.raw as Record<string, unknown> | null;
        const data = rawData ?? {
          cpu: { percent: latest.cpu },
          memory: { percent: latest.memory },
          disk: { percent: latest.disk },
          network: latest.network,
          gpu: latest.gpu != null
            ? [{ gpu_utilization_percent: latest.gpu, memory_percent: latest.gpuMemory ?? 0 }]
            : null,
        };
        sendToClient(ws, {
          type: "agent_metrics",
          agentId: msg.agentId,
          timestamp: latest.timestamp.toISOString(),
          data,
        });
      }
      break;
    }
    case "unsubscribe": {
      unsubscribeDashboardFromAgent(ws, msg.agentId);
      break;
    }
    case "training_stop": {
      const agentConn = getAgentConnection(msg.agentId);
      if (!agentConn) {
        sendToClient(ws, { type: "error", message: "Agent not connected" });
        return;
      }
      if (agentConn.userId !== user.id) {
        sendToClient(ws, { type: "error", message: "Not your agent" });
        return;
      }
      sendToClient(agentConn.ws, {
        type: "training_stop",
        taskId: msg.taskId,
        signal: "SIGINT",
      });
      const { agentId, taskId } = msg;
      const timeout = setTimeout(() => {
        const conn = getAgentConnection(agentId);
        if (conn) {
          sendToClient(conn.ws, {
            type: "training_kill",
            taskId,
            signal: "SIGKILL",
          });
        }
        clearPendingTrainingStop(taskId);
      }, TRAINING_STOP_GRACE_MS);
      setPendingTrainingStop(taskId, timeout);
      break;
    }
  }
}
