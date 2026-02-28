import { prisma } from "../lib/prisma.js";
import { Prisma } from "@prisma/client";
import { MAX_EVENTS_PER_AGENT } from "../constants.js";
import { logger } from "../lib/logger.js";

interface CreateEventInput {
  agentId: string;
  type: string;
  source?: string;
  severity?: string | null;
  message: string;
  data?: unknown;
}

export async function createEvent(input: CreateEventInput): Promise<void> {
  await prisma.event.create({
    data: {
      agentId: input.agentId,
      type: input.type,
      source: input.source ?? "agent",
      severity: input.severity ?? null,
      message: input.message,
      data: input.data ? (input.data as object) : undefined,
    },
  });
}

export async function pruneEvents(agentId: string): Promise<void> {
  try {
    const count = await prisma.event.count({ where: { agentId } });
    if (count <= MAX_EVENTS_PER_AGENT) return;

    const toDelete = count - MAX_EVENTS_PER_AGENT;
    const oldest = await prisma.event.findMany({
      where: { agentId },
      orderBy: { timestamp: "asc" },
      take: toDelete,
      select: { id: true },
    });

    if (oldest.length > 0) {
      await prisma.event.deleteMany({
        where: { id: { in: oldest.map((e) => e.id) } },
      });
      logger.debug({ agentId, deleted: oldest.length }, "Pruned old events");
    }
  } catch (err) {
    logger.warn({ err, agentId }, "Failed to prune events");
  }
}

export async function queryEvents(
  userId: string,
  params: { limit: number; offset: number; type?: string; severity?: string; agentId?: string }
): Promise<{ events: unknown[]; total: number }> {
  // Get user's agent IDs for scoping
  const agents = await prisma.agent.findMany({
    where: { userId },
    select: { id: true },
  });
  const agentIds = agents.map((a) => a.id);

  const where: Prisma.EventWhereInput = {
    agentId: params.agentId ? { equals: params.agentId, in: agentIds } : { in: agentIds },
    ...(params.type && { type: params.type }),
    ...(params.severity && { severity: params.severity }),
  };

  const [events, total] = await Promise.all([
    prisma.event.findMany({
      where,
      orderBy: { timestamp: "desc" },
      take: params.limit,
      skip: params.offset,
      include: { agent: { select: { name: true } } },
    }),
    prisma.event.count({ where }),
  ]);

  return { events, total };
}

export async function searchEvents(
  userId: string,
  query: string,
  limit: number,
  offset: number
): Promise<{ events: unknown[]; total: number }> {
  const agents = await prisma.agent.findMany({
    where: { userId },
    select: { id: true },
  });
  const agentIds = agents.map((a) => a.id);

  if (agentIds.length === 0) {
    return { events: [], total: 0 };
  }

  // Use tsvector full-text search
  const events = await prisma.$queryRaw<Array<Record<string, unknown>>>`
    SELECT e.*, a."name" as "agentName"
    FROM "Event" e
    JOIN "Agent" a ON e."agentId" = a."id"
    WHERE e."search_vector" @@ plainto_tsquery('english', ${query})
      AND e."agentId" = ANY(${agentIds})
    ORDER BY ts_rank(e."search_vector", plainto_tsquery('english', ${query})) DESC, e."timestamp" DESC
    LIMIT ${limit} OFFSET ${offset}
  `;

  const countResult = await prisma.$queryRaw<Array<{ count: bigint }>>`
    SELECT COUNT(*) as count
    FROM "Event" e
    WHERE e."search_vector" @@ plainto_tsquery('english', ${query})
      AND e."agentId" = ANY(${agentIds})
  `;

  const total = Number(countResult[0]?.count ?? 0);

  return { events, total };
}

export async function getAgentEvents(
  agentId: string,
  params: { limit: number; offset: number; type?: string; severity?: string }
): Promise<{ events: unknown[]; total: number }> {
  const where: Prisma.EventWhereInput = {
    agentId,
    ...(params.type && { type: params.type }),
    ...(params.severity && { severity: params.severity }),
  };

  const [events, total] = await Promise.all([
    prisma.event.findMany({
      where,
      orderBy: { timestamp: "desc" },
      take: params.limit,
      skip: params.offset,
    }),
    prisma.event.count({ where }),
  ]);

  return { events, total };
}

export async function getTimeline(
  userId: string,
  limit: number,
  offset: number
): Promise<{ events: unknown[]; total: number }> {
  const agents = await prisma.agent.findMany({
    where: { userId },
    select: { id: true },
  });
  const agentIds = agents.map((a) => a.id);

  const where: Prisma.EventWhereInput = { agentId: { in: agentIds } };

  const [events, total] = await Promise.all([
    prisma.event.findMany({
      where,
      orderBy: { timestamp: "desc" },
      take: limit,
      skip: offset,
      include: { agent: { select: { name: true } } },
    }),
    prisma.event.count({ where }),
  ]);

  return { events, total };
}
