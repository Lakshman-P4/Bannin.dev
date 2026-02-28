import { Router } from "express";
import { VERSION } from "../constants.js";
import { getConnectedAgentCount } from "../ws/registry.js";

const router = Router();

router.get("/", (_req, res) => {
  res.json({
    status: "ok",
    timestamp: new Date().toISOString(),
    version: VERSION,
    agents_connected: getConnectedAgentCount(),
  });
});

export default router;
