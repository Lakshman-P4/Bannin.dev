import express from "express";
import helmet from "helmet";
import compression from "compression";
import cors from "cors";
import pinoHttp from "pino-http";
import { getEnv } from "./config/env.js";
import { logger } from "./lib/logger.js";
import { createGlobalLimiter } from "./middleware/rateLimiter.js";
import { errorHandler } from "./middleware/errorHandler.js";

import { createAuthRoutes } from "./routes/auth.routes.js";
import agentsRoutes from "./routes/agents.routes.js";
import dashboardRoutes, { agentDataRouter } from "./routes/dashboard.routes.js";
import eventsRoutes from "./routes/events.routes.js";
import notificationsRoutes from "./routes/notifications.routes.js";
import healthRoutes from "./routes/health.routes.js";

export function createApp(): express.Express {
  const app = express();
  const env = getEnv();

  // Security
  app.use(helmet());
  app.use(compression());
  app.use(cors({
    origin: env.ALLOWED_ORIGINS.split(",").map((o) => o.trim()),
    credentials: true,
  }));

  // Parsing
  app.use(express.json({ limit: "1mb" }));

  // Logging
  app.use(pinoHttp({ logger, autoLogging: { ignore: (req) => req.url === "/api/health" } }));

  // Rate limiting (fresh per app instance so tests get clean stores)
  app.use(createGlobalLimiter());

  // Routes
  app.use("/api/health", healthRoutes);
  app.use("/api/auth", createAuthRoutes());
  app.use("/api/agents", agentsRoutes);
  app.use("/api/agents/:id", agentDataRouter);
  app.use("/api/dashboard", dashboardRoutes);
  app.use("/api/events", eventsRoutes);
  app.use("/api/notifications", notificationsRoutes);

  // 404
  app.use((_req, res) => {
    res.status(404).json({ error: { code: "NOT_FOUND", message: "Endpoint not found" } });
  });

  // Error handler (must be last)
  app.use(errorHandler);

  return app;
}
