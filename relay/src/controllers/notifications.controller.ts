import type { Request, Response, NextFunction } from "express";
import * as pushService from "../services/push.service.js";
import type { PushSubscribeInput, PushUnsubscribeInput } from "../schemas/notifications.schema.js";

export async function subscribe(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as PushSubscribeInput;
    await pushService.subscribe(req.user!.id, input);
    res.status(201).json({ data: { message: "Subscription registered" } });
  } catch (err) {
    next(err);
  }
}

export async function unsubscribe(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as PushUnsubscribeInput;
    await pushService.unsubscribe(req.user!.id, input.endpoint);
    res.json({ data: { message: "Subscription removed" } });
  } catch (err) {
    next(err);
  }
}

export async function testNotification(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    await pushService.sendTestNotification(req.user!.id);
    res.json({ data: { message: "Test notification sent" } });
  } catch (err) {
    next(err);
  }
}
