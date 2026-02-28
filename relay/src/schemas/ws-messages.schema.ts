import { z } from "zod";

// Agent -> Relay message schemas (all 8 types)

const metricsDataSchema = z.object({
  cpu: z.object({
    percent: z.number(),
    per_core: z.array(z.number()),
    count_physical: z.number(),
    count_logical: z.number(),
    frequency_mhz: z.number().nullable(),
  }),
  memory: z.object({
    total_gb: z.number(),
    available_gb: z.number(),
    used_gb: z.number(),
    percent: z.number(),
  }),
  disk: z.object({
    total_gb: z.number(),
    used_gb: z.number(),
    free_gb: z.number(),
    percent: z.number(),
  }),
  network: z.object({
    bytes_sent: z.number(),
    bytes_received: z.number(),
    bytes_sent_mb: z.number(),
    bytes_received_mb: z.number(),
  }),
  gpu: z
    .array(
      z.object({
        index: z.number(),
        name: z.string(),
        memory_total_mb: z.number(),
        memory_used_mb: z.number(),
        memory_free_mb: z.number(),
        memory_percent: z.number(),
        gpu_utilization_percent: z.number(),
        temperature_c: z.number().nullable(),
      })
    )
    .nullable()
    .optional(),
});

const alertDataSchema = z.object({
  id: z.string(),
  severity: z.enum(["info", "warning", "critical"]),
  message: z.string(),
  value: z.number(),
  threshold: z.number().nullable(),
  fired_at: z.string(),
  fired_epoch: z.number(),
});

const oomPredictionDataSchema = z.object({
  ram: z.object({
    current_percent: z.number().nullable(),
    trend: z.string(),
    growth_rate_per_min: z.number().optional(),
    confidence: z.number().optional(),
    data_points: z.number().optional(),
    minutes_until_full: z.number().nullable(),
    estimated_full_at: z.string().nullable().optional(),
    severity: z.string().optional(),
  }),
  gpu: z.array(z.record(z.unknown())).default([]),
  data_points: z.number(),
  min_data_points_required: z.number(),
});

const trainingDataSchema = z.object({
  active_tasks: z.array(z.record(z.unknown())).default([]),
  completed_tasks: z.array(z.record(z.unknown())).default([]),
  stalled_tasks: z.array(z.record(z.unknown())).default([]),
  detected_tasks: z.array(z.record(z.unknown())).default([]),
  total_tracked: z.number(),
});

const eventDataSchema = z.object({
  ts: z.number(),
  source: z.string(),
  machine: z.string(),
  type: z.string(),
  severity: z.string().nullable(),
  data: z.record(z.unknown()).default({}),
  message: z.string(),
});

const processesDataSchema = z.object({
  summary: z.object({
    total: z.number(),
    running: z.number(),
    sleeping: z.number(),
  }),
  top_processes: z.array(z.record(z.unknown())).default([]),
  resource_breakdown: z
    .object({
      cpu: z.array(z.record(z.unknown())).default([]),
      ram: z.array(z.record(z.unknown())).default([]),
    })
    .default({ cpu: [], ram: [] }),
});

const healthDataSchema = z.object({
  health_score: z.number(),
  rating: z.string(),
  source: z.string().optional(),
  components: z.record(z.unknown()).default({}),
  recommendation: z.string().nullable(),
  per_source: z.array(z.record(z.unknown())).optional(),
});

const heartbeatDataSchema = z.object({
  uptime_seconds: z.number(),
});

// Union of all agent message types
export const agentMessageSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("metrics"), timestamp: z.string(), data: metricsDataSchema }),
  z.object({ type: z.literal("alert"), timestamp: z.string(), data: alertDataSchema }),
  z.object({ type: z.literal("oom_prediction"), timestamp: z.string(), data: oomPredictionDataSchema }),
  z.object({ type: z.literal("training"), timestamp: z.string(), data: trainingDataSchema }),
  z.object({ type: z.literal("event"), timestamp: z.string(), data: eventDataSchema }),
  z.object({ type: z.literal("processes"), timestamp: z.string(), data: processesDataSchema }),
  z.object({ type: z.literal("health"), timestamp: z.string(), data: healthDataSchema }),
  z.object({ type: z.literal("heartbeat"), timestamp: z.string(), data: heartbeatDataSchema }),
]);

// Agent -> Relay: training stopped confirmation
export const trainingStoppedSchema = z.object({
  type: z.literal("training_stopped"),
  taskId: z.string(),
  status: z.enum(["graceful", "forced"]),
});

// Dashboard -> Relay message schemas
export const dashboardMessageSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("subscribe"), agentId: z.string().uuid() }),
  z.object({ type: z.literal("unsubscribe"), agentId: z.string().uuid() }),
  z.object({ type: z.literal("training_stop"), agentId: z.string().uuid(), taskId: z.string() }),
]);

export type AgentMessage = z.infer<typeof agentMessageSchema>;
export type DashboardMessage = z.infer<typeof dashboardMessageSchema>;
