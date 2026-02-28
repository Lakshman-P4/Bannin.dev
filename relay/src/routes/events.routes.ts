import { Router } from "express";
import * as eventsController from "../controllers/events.controller.js";
import { authMiddleware } from "../middleware/auth.js";
import { validate } from "../middleware/validate.js";
import { eventQuerySchema, eventSearchSchema } from "../schemas/events.schema.js";

const router = Router();

router.use(authMiddleware);

router.get("/", validate(eventQuerySchema, "query"), eventsController.queryEvents);
router.get("/search", validate(eventSearchSchema, "query"), eventsController.searchEvents);
router.get("/timeline", eventsController.timeline);

export default router;
