import { createServer } from "node:http";
import { WebSocketServer } from "ws";
import { getEnv } from "./config/env.js";
import { logger } from "./lib/logger.js";
import { prisma, runTsvectorMigration } from "./lib/prisma.js";
import { getRedis, closeRedis } from "./lib/redis.js";
import { createApp } from "./app.js";
import { handleAgentConnection } from "./ws/agentHandler.js";
import { handleDashboardConnection } from "./ws/dashboardHandler.js";
import { VERSION, SNAPSHOT_PRUNE_INTERVAL_MS } from "./constants.js";
import { pruneSnapshots } from "./services/metrics.service.js";
import { pruneEvents } from "./services/events.service.js";
import { pruneAlerts } from "./services/alerts.service.js";

async function main(): Promise<void> {
  const env = getEnv();
  const app = createApp();
  const server = createServer(app);

  // Connect to databases
  await prisma.$connect();
  logger.info("PostgreSQL connected");

  const redis = getRedis();
  await redis.connect();
  logger.info("Redis connected");

  // Run tsvector migration (idempotent)
  await runTsvectorMigration();

  // WebSocket servers
  const agentWss = new WebSocketServer({ noServer: true });
  const dashboardWss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (req, socket, head) => {
    const url = req.url ?? "";
    if (url.startsWith("/ws/agent")) {
      agentWss.handleUpgrade(req, socket, head, (ws) => {
        void handleAgentConnection(ws, req);
      });
    } else if (url.startsWith("/ws/dashboard")) {
      dashboardWss.handleUpgrade(req, socket, head, (ws) => {
        void handleDashboardConnection(ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  // Periodic pruning for ALL agents (snapshots, events, alerts)
  const pruneInterval = setInterval(async () => {
    try {
      const agents = await prisma.agent.findMany({ select: { id: true } });
      for (const agent of agents) {
        await pruneSnapshots(agent.id);
        await pruneEvents(agent.id);
        await pruneAlerts(agent.id);
      }
    } catch (err) {
      logger.warn({ err }, "Periodic pruning failed");
    }
  }, SNAPSHOT_PRUNE_INTERVAL_MS);

  // Graceful shutdown
  const shutdown = async (): Promise<void> => {
    logger.info("Shutting down...");
    clearInterval(pruneInterval);

    server.close();
    agentWss.close();
    dashboardWss.close();

    await prisma.$disconnect();
    await closeRedis();

    logger.info("Shutdown complete");
    process.exit(0);
  };

  process.on("SIGTERM", () => void shutdown());
  process.on("SIGINT", () => void shutdown());

  server.listen(env.PORT, () => {
    logger.info(`
  Bannin Relay v${VERSION}
  API:        http://localhost:${env.PORT}
  WebSocket:  ws://localhost:${env.PORT}/ws/agent
  Dashboard:  ws://localhost:${env.PORT}/ws/dashboard
  Health:     http://localhost:${env.PORT}/api/health
  Environment: ${env.NODE_ENV}
`);
  });
}

main().catch((err) => {
  logger.fatal({ err }, "Failed to start server");
  process.exit(1);
});
