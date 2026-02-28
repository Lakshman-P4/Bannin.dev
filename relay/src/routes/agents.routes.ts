import { Router } from "express";
import * as agentsController from "../controllers/agents.controller.js";
import { authMiddleware } from "../middleware/auth.js";
import { validate } from "../middleware/validate.js";
import { createAgentSchema, updateAgentSchema } from "../schemas/agents.schema.js";

const router = Router();

router.use(authMiddleware);

router.get("/", agentsController.list);
router.post("/", validate(createAgentSchema), agentsController.create);
router.get("/:id", agentsController.get);
router.patch("/:id", validate(updateAgentSchema), agentsController.update);
router.delete("/:id", agentsController.remove);
router.post("/:id/regenerate-key", agentsController.regenerateKey);

export default router;
