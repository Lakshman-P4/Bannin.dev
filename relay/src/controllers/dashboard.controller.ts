import type { Request, Response, NextFunction } from "express";
import { prisma } from "../lib/prisma.js";
import { paramId } from "../lib/params.js";
import * as metricsService from "../services/metrics.service.js";
import * as alertsService from "../services/alerts.service.js";
import * as eventsService from "../services/events.service.js";
import type { MetricsHistoryQuery, AlertQuery, EventQuery } from "../schemas/events.schema.js";

export async function dashboard(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agents = await prisma.agent.findMany({
      where: { userId: req.user!.id },
      select: {
        id: true,
        name: true,
        hostname: true,
        isOnline: true,
        lastSeen: true,
        snapshots: { orderBy: { timestamp: "desc" }, take: 1 },
        _count: { select: { alerts: { where: { resolvedAt: null } } } },
      },
      orderBy: { createdAt: "desc" },
    });

    const data = agents.map((a) => ({
      id: a.id,
      name: a.name,
      hostname: a.hostname,
      isOnline: a.isOnline,
      lastSeen: a.lastSeen,
      latestMetrics: a.snapshots[0] ?? null,
      activeAlerts: a._count.alerts,
    }));

    res.json({ data });
  } catch (err) {
    next(err);
  }
}

export async function agentMetrics(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    const ok = await ensureAgentOwnership(req.user!.id, agentId, res);
    if (!ok) return;

    const snapshot = await metricsService.getLatestSnapshot(agentId);
    res.json({ data: snapshot });
  } catch (err) {
    next(err);
  }
}

export async function agentMetricsHistory(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    const ok = await ensureAgentOwnership(req.user!.id, agentId, res);
    if (!ok) return;

    const params = req.query as unknown as MetricsHistoryQuery;
    const { snapshots, total } = await metricsService.getSnapshotHistory(agentId, params.minutes, params.limit, params.offset);
    res.json({ data: snapshots, meta: { total, limit: params.limit, offset: params.offset } });
  } catch (err) {
    next(err);
  }
}

export async function agentProcesses(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    const ok = await ensureAgentOwnership(req.user!.id, agentId, res);
    if (!ok) return;

    const snapshot = await prisma.metricSnapshot.findFirst({
      where: { agentId },
      orderBy: { timestamp: "desc" },
      select: { processes: true, timestamp: true },
    });

    res.json({ data: snapshot?.processes ?? null });
  } catch (err) {
    next(err);
  }
}

export async function agentAlerts(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    const ok = await ensureAgentOwnership(req.user!.id, agentId, res);
    if (!ok) return;

    const params = req.query as unknown as AlertQuery;
    const { alerts, total } = await alertsService.getAgentAlerts(agentId, params);
    res.json({ data: alerts, meta: { total, limit: params.limit, offset: params.offset } });
  } catch (err) {
    next(err);
  }
}

export async function agentEvents(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    const ok = await ensureAgentOwnership(req.user!.id, agentId, res);
    if (!ok) return;

    const params = req.query as unknown as EventQuery;
    const { events, total } = await eventsService.getAgentEvents(agentId, params);
    res.json({ data: events, meta: { total, limit: params.limit, offset: params.offset } });
  } catch (err) {
    next(err);
  }
}

async function ensureAgentOwnership(userId: string, agentId: string, res: Response): Promise<boolean> {
  const agent = await prisma.agent.findFirst({ where: { id: agentId, userId } });
  if (!agent) {
    res.status(404).json({ error: { code: "NOT_FOUND", message: "Agent not found" } });
    return false;
  }
  return true;
}
