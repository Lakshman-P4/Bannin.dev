import { Router } from "express";
import * as dashboardController from "../controllers/dashboard.controller.js";
import { authMiddleware } from "../middleware/auth.js";
import { validate } from "../middleware/validate.js";
import { metricsHistorySchema, alertQuerySchema, eventQuerySchema } from "../schemas/events.schema.js";

const router = Router();

router.use(authMiddleware);

router.get("/", dashboardController.dashboard);

// Agent-scoped data endpoints are mounted under /api/agents/:id in app.ts
export const agentDataRouter = Router({ mergeParams: true });
agentDataRouter.use(authMiddleware);
agentDataRouter.get("/metrics", dashboardController.agentMetrics);
agentDataRouter.get("/metrics/history", validate(metricsHistorySchema, "query"), dashboardController.agentMetricsHistory);
agentDataRouter.get("/processes", dashboardController.agentProcesses);
agentDataRouter.get("/alerts", validate(alertQuerySchema, "query"), dashboardController.agentAlerts);
agentDataRouter.get("/events", validate(eventQuerySchema, "query"), dashboardController.agentEvents);

export default router;
