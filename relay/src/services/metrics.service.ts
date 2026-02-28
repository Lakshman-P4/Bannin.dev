import { prisma } from "../lib/prisma.js";
import { MAX_SNAPSHOTS_PER_AGENT } from "../constants.js";
import { logger } from "../lib/logger.js";

interface MetricsData {
  cpu: { percent: number };
  memory: { percent: number };
  disk: { percent: number };
  gpu?: Array<{ memory_percent: number; gpu_utilization_percent: number }> | null;
  network?: Record<string, unknown>;
}

export async function persistSnapshot(agentId: string, data: MetricsData, processes?: unknown): Promise<void> {
  const gpu0 = data.gpu?.[0];

  await prisma.metricSnapshot.create({
    data: {
      agentId,
      cpu: data.cpu.percent,
      memory: data.memory.percent,
      disk: data.disk.percent,
      gpu: gpu0?.gpu_utilization_percent ?? null,
      gpuMemory: gpu0?.memory_percent ?? null,
      network: data.network ? (data.network as object) : undefined,
      processes: processes ? (processes as object) : undefined,
      raw: data as object,
    },
  });
}

export async function pruneSnapshots(agentId: string): Promise<void> {
  try {
    const count = await prisma.metricSnapshot.count({ where: { agentId } });
    if (count <= MAX_SNAPSHOTS_PER_AGENT) return;

    const toDelete = count - MAX_SNAPSHOTS_PER_AGENT;
    const oldest = await prisma.metricSnapshot.findMany({
      where: { agentId },
      orderBy: { timestamp: "asc" },
      take: toDelete,
      select: { id: true },
    });

    if (oldest.length > 0) {
      await prisma.metricSnapshot.deleteMany({
        where: { id: { in: oldest.map((s) => s.id) } },
      });
      logger.debug({ agentId, deleted: oldest.length }, "Pruned old metric snapshots");
    }
  } catch (err) {
    logger.warn({ err, agentId }, "Failed to prune snapshots");
  }
}

export async function getLatestSnapshot(agentId: string): Promise<unknown | null> {
  return prisma.metricSnapshot.findFirst({
    where: { agentId },
    orderBy: { timestamp: "desc" },
  });
}

export async function getSnapshotHistory(agentId: string, minutes: number, limit: number, offset: number): Promise<{ snapshots: unknown[]; total: number }> {
  const since = new Date(Date.now() - minutes * 60 * 1000);

  const [snapshots, total] = await Promise.all([
    prisma.metricSnapshot.findMany({
      where: { agentId, timestamp: { gte: since } },
      orderBy: { timestamp: "desc" },
      take: limit,
      skip: offset,
    }),
    prisma.metricSnapshot.count({
      where: { agentId, timestamp: { gte: since } },
    }),
  ]);

  return { snapshots, total };
}
