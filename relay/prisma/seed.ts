import { createHash } from "node:crypto";
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();
const KEY_PREFIX_LENGTH = 16;

async function main(): Promise<void> {
  // Demo user WITH email
  const demoHash = await bcrypt.hash("demo1234", 12);
  const demoUser = await prisma.user.upsert({
    where: { username: "demo" },
    update: {},
    create: {
      username: "demo",
      displayName: "Demo User",
      email: "demo@bannin.dev",
      passwordHash: demoHash,
      emailVerified: true,
    },
  });

  // Demo user WITHOUT email
  const guestHash = await bcrypt.hash("guest1234", 12);
  await prisma.user.upsert({
    where: { username: "guest" },
    update: {},
    create: {
      username: "guest",
      displayName: "Guest User",
      passwordHash: guestHash,
      emailVerified: false,
    },
  });

  // Demo agent with known API key (for demo user)
  const rawKey = "ban_demo_key_for_testing_only_do_not_use_in_production";
  const apiKeyHash = await bcrypt.hash(rawKey, 12);
  const keyPrefix = createHash("sha256").update(rawKey).digest("hex").slice(0, KEY_PREFIX_LENGTH);

  const existingAgent = await prisma.agent.findFirst({
    where: { userId: demoUser.id, name: "Demo MacBook" },
  });

  const agent = existingAgent ?? await prisma.agent.create({
    data: {
      userId: demoUser.id,
      name: "Demo MacBook",
      apiKeyHash,
      keyPrefix,
      hostname: "demo-macbook.local",
      os: "macOS",
      agentVersion: "0.1.0",
      lastSeen: new Date(),
      isOnline: false,
    },
  });

  // Only seed data if the agent was just created (no existing snapshots)
  const snapshotCount = await prisma.metricSnapshot.count({ where: { agentId: agent.id } });
  if (snapshotCount > 0) {
    console.log("Seed: demo data already exists, skipping");
    return;
  }

  // Sample metric snapshots (50 over the last hour)
  const now = Date.now();
  for (let i = 0; i < 50; i++) {
    const timestamp = new Date(now - (50 - i) * 72_000);
    await prisma.metricSnapshot.create({
      data: {
        agentId: agent.id,
        timestamp,
        cpu: 20 + Math.random() * 40,
        memory: 55 + Math.random() * 25,
        disk: 45 + Math.random() * 10,
        gpu: Math.random() > 0.5 ? 30 + Math.random() * 50 : null,
        gpuMemory: Math.random() > 0.5 ? 40 + Math.random() * 40 : null,
        network: { bytes_sent: Math.floor(Math.random() * 1e9), bytes_received: Math.floor(Math.random() * 1e9) },
      },
    });
  }

  // Sample events
  const events = [
    { type: "alert", source: "alerts", severity: "critical", message: "RAM at 94% -- OOM likely in ~8 minutes" },
    { type: "alert", source: "alerts", severity: "critical", message: "GPU memory at 96% -- VRAM exhaustion imminent" },
    { type: "alert", source: "alerts", severity: "warning", message: "CPU sustained above 85% for 10 minutes" },
    { type: "alert", source: "alerts", severity: "warning", message: "Disk usage at 82%" },
    { type: "training", source: "progress", severity: "info", message: "Training complete: fine-tune-llama finished in 3h 42m" },
    { type: "training", source: "progress", severity: "info", message: "Training complete: image-classifier finished in 45m" },
    { type: "training", source: "progress", severity: "warning", message: "Training stalled: data-pipeline -- no progress for 15m" },
    { type: "oom_prediction", source: "oom", severity: "warning", message: "OOM prediction: RAM at 78%, growing at 2.1%/min" },
    { type: "oom_prediction", source: "oom", severity: "critical", message: "OOM prediction: RAM at 91%, ~6 minutes until full" },
    { type: "session", source: "system", severity: "info", message: "Agent started on demo-macbook.local" },
  ];

  for (const [i, event] of events.entries()) {
    await prisma.event.create({
      data: {
        agentId: agent.id,
        timestamp: new Date(now - (events.length - i) * 600_000),
        ...event,
      },
    });
  }

  // Sample alerts
  await prisma.alertHistory.create({
    data: {
      agentId: agent.id,
      severity: "critical",
      message: "RAM at 94%",
      value: 94,
      threshold: 90,
    },
  });
  await prisma.alertHistory.create({
    data: {
      agentId: agent.id,
      severity: "warning",
      message: "CPU at 87%",
      value: 87,
      threshold: 85,
    },
  });

  console.log("Seed complete: demo + guest users, agent, 50 snapshots, 10 events, 2 alerts");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
