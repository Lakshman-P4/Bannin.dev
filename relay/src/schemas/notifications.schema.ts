import { z } from "zod";

export const pushSubscribeSchema = z.object({
  endpoint: z.string().url("Invalid endpoint URL"),
  keys: z.object({
    p256dh: z.string().min(1, "p256dh key is required"),
    auth: z.string().min(1, "auth key is required"),
  }),
});

export const pushUnsubscribeSchema = z.object({
  endpoint: z.string().url("Invalid endpoint URL"),
});

export type PushSubscribeInput = z.infer<typeof pushSubscribeSchema>;
export type PushUnsubscribeInput = z.infer<typeof pushUnsubscribeSchema>;
