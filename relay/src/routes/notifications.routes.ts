import { Router } from "express";
import * as notificationsController from "../controllers/notifications.controller.js";
import { authMiddleware } from "../middleware/auth.js";
import { validate } from "../middleware/validate.js";
import { pushSubscribeSchema, pushUnsubscribeSchema } from "../schemas/notifications.schema.js";

const router = Router();

router.use(authMiddleware);

router.post("/push/subscribe", validate(pushSubscribeSchema), notificationsController.subscribe);
router.delete("/push/unsubscribe", validate(pushUnsubscribeSchema), notificationsController.unsubscribe);
router.post("/test", notificationsController.testNotification);

export default router;
