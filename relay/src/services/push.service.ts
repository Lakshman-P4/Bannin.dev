import webpush from "web-push";
import { prisma } from "../lib/prisma.js";
import { getEnv } from "../config/env.js";
import { MAX_PUSH_SUBS_PER_USER } from "../constants.js";
import { logger } from "../lib/logger.js";

let _configured = false;

function ensureConfigured(): boolean {
  if (_configured) return true;
  const env = getEnv();
  if (!env.VAPID_PUBLIC_KEY || !env.VAPID_PRIVATE_KEY || !env.VAPID_EMAIL) {
    return false;
  }
  webpush.setVapidDetails(env.VAPID_EMAIL, env.VAPID_PUBLIC_KEY, env.VAPID_PRIVATE_KEY);
  _configured = true;
  return true;
}

export async function subscribe(userId: string, subscription: { endpoint: string; keys: { p256dh: string; auth: string } }): Promise<void> {
  const count = await prisma.pushSubscription.count({ where: { userId } });
  if (count >= MAX_PUSH_SUBS_PER_USER) {
    throw new Error(`Maximum ${MAX_PUSH_SUBS_PER_USER} push subscriptions per account`);
  }

  await prisma.pushSubscription.upsert({
    where: { endpoint: subscription.endpoint },
    create: {
      userId,
      endpoint: subscription.endpoint,
      keys: subscription.keys as object,
    },
    update: {
      keys: subscription.keys as object,
    },
  });
}

export async function unsubscribe(userId: string, endpoint: string): Promise<void> {
  await prisma.pushSubscription.deleteMany({
    where: { userId, endpoint },
  });
}

export async function sendNotification(userId: string, payload: { title: string; body: string; data?: Record<string, unknown> }): Promise<void> {
  if (!ensureConfigured()) {
    logger.debug("Push notifications not configured (VAPID keys missing)");
    return;
  }

  const subs = await prisma.pushSubscription.findMany({ where: { userId } });
  if (subs.length === 0) return;

  const payloadStr = JSON.stringify(payload);

  for (const sub of subs) {
    try {
      const keys = sub.keys as { p256dh: string; auth: string };
      await webpush.sendNotification(
        {
          endpoint: sub.endpoint,
          keys: { p256dh: keys.p256dh, auth: keys.auth },
        },
        payloadStr
      );
    } catch (err) {
      const statusCode = (err as { statusCode?: number }).statusCode;
      if (statusCode === 404 || statusCode === 410) {
        // Subscription expired or unsubscribed
        await prisma.pushSubscription.delete({ where: { id: sub.id } }).catch(() => {});
        logger.info({ endpoint: sub.endpoint }, "Removed expired push subscription");
      } else {
        logger.warn({ err, endpoint: sub.endpoint }, "Failed to send push notification");
      }
    }
  }
}

export async function sendTestNotification(userId: string): Promise<void> {
  await sendNotification(userId, {
    title: "Bannin",
    body: "Push notifications are working! You'll receive alerts here.",
    data: { type: "test" },
  });
}
