import { prisma } from "../lib/prisma.js";
import { Prisma } from "@prisma/client";
import { MAX_ALERTS_PER_AGENT } from "../constants.js";
import { logger } from "../lib/logger.js";

interface AlertInput {
  agentId: string;
  severity: string;
  message: string;
  value?: number | null;
  threshold?: number | null;
}

export async function persistAlert(input: AlertInput): Promise<void> {
  await prisma.alertHistory.create({
    data: {
      agentId: input.agentId,
      severity: input.severity,
      message: input.message,
      value: input.value ?? null,
      threshold: input.threshold ?? null,
    },
  });
}

export async function pruneAlerts(agentId: string): Promise<void> {
  try {
    const count = await prisma.alertHistory.count({ where: { agentId } });
    if (count <= MAX_ALERTS_PER_AGENT) return;

    const toDelete = count - MAX_ALERTS_PER_AGENT;
    const oldest = await prisma.alertHistory.findMany({
      where: { agentId },
      orderBy: { firedAt: "asc" },
      take: toDelete,
      select: { id: true },
    });

    if (oldest.length > 0) {
      await prisma.alertHistory.deleteMany({
        where: { id: { in: oldest.map((a) => a.id) } },
      });
      logger.debug({ agentId, deleted: oldest.length }, "Pruned old alerts");
    }
  } catch (err) {
    logger.warn({ err, agentId }, "Failed to prune alerts");
  }
}

export async function getAgentAlerts(
  agentId: string,
  params: { limit: number; offset: number; severity?: string }
): Promise<{ alerts: unknown[]; total: number }> {
  const where: Prisma.AlertHistoryWhereInput = {
    agentId,
    ...(params.severity && { severity: params.severity }),
  };

  const [alerts, total] = await Promise.all([
    prisma.alertHistory.findMany({
      where,
      orderBy: { firedAt: "desc" },
      take: params.limit,
      skip: params.offset,
    }),
    prisma.alertHistory.count({ where }),
  ]);

  return { alerts, total };
}
