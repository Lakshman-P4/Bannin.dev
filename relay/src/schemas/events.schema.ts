import { z } from "zod";
import { EVENTS_PAGE_LIMIT } from "../constants.js";

export const eventQuerySchema = z.object({
  limit: z.coerce.number().min(1).max(EVENTS_PAGE_LIMIT).default(50),
  offset: z.coerce.number().min(0).default(0),
  type: z.string().optional(),
  severity: z.string().optional(),
  agentId: z.string().uuid().optional(),
});

export const eventSearchSchema = z.object({
  q: z.string().min(1, "Search query is required").max(500),
  limit: z.coerce.number().min(1).max(EVENTS_PAGE_LIMIT).default(50),
  offset: z.coerce.number().min(0).default(0),
});

export const metricsHistorySchema = z.object({
  minutes: z.coerce.number().min(1).max(1440).default(30),
  limit: z.coerce.number().min(1).max(EVENTS_PAGE_LIMIT).default(100),
  offset: z.coerce.number().min(0).default(0),
});

export const alertQuerySchema = z.object({
  limit: z.coerce.number().min(1).max(EVENTS_PAGE_LIMIT).default(50),
  offset: z.coerce.number().min(0).default(0),
  severity: z.string().optional(),
});

export type EventQuery = z.infer<typeof eventQuerySchema>;
export type EventSearch = z.infer<typeof eventSearchSchema>;
export type MetricsHistoryQuery = z.infer<typeof metricsHistorySchema>;
export type AlertQuery = z.infer<typeof alertQuerySchema>;
