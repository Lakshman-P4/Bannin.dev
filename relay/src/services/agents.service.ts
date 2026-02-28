import { randomBytes, createHash } from "node:crypto";
import bcrypt from "bcryptjs";
import { prisma } from "../lib/prisma.js";
import { BCRYPT_ROUNDS, MAX_AGENTS_PER_USER, KEY_PREFIX_LENGTH } from "../constants.js";
import { NotFoundError, LimitError } from "../lib/errors.js";
import type { CreateAgentInput, UpdateAgentInput } from "../schemas/agents.schema.js";

export async function listAgents(userId: string): Promise<Array<{
  id: string;
  name: string;
  hostname: string | null;
  os: string | null;
  agentVersion: string | null;
  lastSeen: Date | null;
  isOnline: boolean;
  createdAt: Date;
}>> {
  return prisma.agent.findMany({
    where: { userId },
    select: {
      id: true,
      name: true,
      hostname: true,
      os: true,
      agentVersion: true,
      lastSeen: true,
      isOnline: true,
      createdAt: true,
    },
    orderBy: { createdAt: "desc" },
  });
}

export async function createAgent(userId: string, input: CreateAgentInput): Promise<{ agent: { id: string; name: string; createdAt: Date }; apiKey: string }> {
  const count = await prisma.agent.count({ where: { userId } });
  if (count >= MAX_AGENTS_PER_USER) {
    throw new LimitError(`Maximum ${MAX_AGENTS_PER_USER} agents per account`);
  }

  const rawKey = `ban_${randomBytes(32).toString("hex")}`;
  const apiKeyHash = await bcrypt.hash(rawKey, BCRYPT_ROUNDS);
  const keyPrefix = computeKeyPrefix(rawKey);

  const agent = await prisma.agent.create({
    data: {
      userId,
      name: input.name,
      apiKeyHash,
      keyPrefix,
    },
  });

  return {
    agent: { id: agent.id, name: agent.name, createdAt: agent.createdAt },
    apiKey: rawKey,
  };
}

export async function getAgent(userId: string, agentId: string): Promise<{
  id: string;
  name: string;
  hostname: string | null;
  os: string | null;
  agentVersion: string | null;
  lastSeen: Date | null;
  isOnline: boolean;
  createdAt: Date;
  latestSnapshot: unknown | null;
}> {
  const agent = await prisma.agent.findFirst({
    where: { id: agentId, userId },
    include: {
      snapshots: {
        orderBy: { timestamp: "desc" },
        take: 1,
      },
    },
  });

  if (!agent) {
    throw new NotFoundError("Agent not found");
  }

  return {
    id: agent.id,
    name: agent.name,
    hostname: agent.hostname,
    os: agent.os,
    agentVersion: agent.agentVersion,
    lastSeen: agent.lastSeen,
    isOnline: agent.isOnline,
    createdAt: agent.createdAt,
    latestSnapshot: agent.snapshots[0] ?? null,
  };
}

export async function updateAgent(userId: string, agentId: string, input: UpdateAgentInput): Promise<{ id: string; name: string }> {
  const agent = await prisma.agent.findFirst({ where: { id: agentId, userId } });
  if (!agent) {
    throw new NotFoundError("Agent not found");
  }

  const updated = await prisma.agent.update({
    where: { id: agentId },
    data: { name: input.name },
  });

  return { id: updated.id, name: updated.name };
}

export async function deleteAgent(userId: string, agentId: string): Promise<void> {
  const agent = await prisma.agent.findFirst({ where: { id: agentId, userId } });
  if (!agent) {
    throw new NotFoundError("Agent not found");
  }

  await prisma.agent.delete({ where: { id: agentId } });
}

export async function regenerateKey(userId: string, agentId: string): Promise<{ apiKey: string }> {
  const agent = await prisma.agent.findFirst({ where: { id: agentId, userId } });
  if (!agent) {
    throw new NotFoundError("Agent not found");
  }

  const rawKey = `ban_${randomBytes(32).toString("hex")}`;
  const apiKeyHash = await bcrypt.hash(rawKey, BCRYPT_ROUNDS);
  const keyPrefix = computeKeyPrefix(rawKey);

  await prisma.agent.update({
    where: { id: agentId },
    data: { apiKeyHash, keyPrefix },
  });

  return { apiKey: rawKey };
}

export async function findAgentByApiKey(rawKey: string): Promise<{ id: string; userId: string; name: string } | null> {
  // Use SHA-256 prefix for O(1) indexed lookup, then bcrypt.compare the candidates
  const prefix = computeKeyPrefix(rawKey);
  const candidates = await prisma.agent.findMany({
    where: { keyPrefix: prefix },
    select: { id: true, userId: true, name: true, apiKeyHash: true },
  });

  for (const agent of candidates) {
    const match = await bcrypt.compare(rawKey, agent.apiKeyHash);
    if (match) {
      return { id: agent.id, userId: agent.userId, name: agent.name };
    }
  }

  return null;
}

function computeKeyPrefix(rawKey: string): string {
  return createHash("sha256").update(rawKey).digest("hex").slice(0, KEY_PREFIX_LENGTH);
}

// Re-export error classes for controller-level status code mapping
export { NotFoundError, LimitError } from "../lib/errors.js";
