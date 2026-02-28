import { describe, it, expect } from "vitest";
import { agentMessageSchema, dashboardMessageSchema } from "../src/schemas/ws-messages.schema.js";

describe("WebSocket message schemas", () => {
  describe("Agent messages", () => {
    it("validates metrics message", () => {
      const msg = {
        type: "metrics",
        timestamp: new Date().toISOString(),
        data: {
          cpu: { percent: 45.2, per_core: [40, 50], count_physical: 8, count_logical: 16, frequency_mhz: 3200 },
          memory: { total_gb: 32, available_gb: 16, used_gb: 16, percent: 50 },
          disk: { total_gb: 500, used_gb: 250, free_gb: 250, percent: 50 },
          network: { bytes_sent: 1000, bytes_received: 2000, bytes_sent_mb: 0.001, bytes_received_mb: 0.002 },
          gpu: null,
        },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates alert message", () => {
      const msg = {
        type: "alert",
        timestamp: new Date().toISOString(),
        data: {
          id: "ram_high",
          severity: "critical",
          message: "RAM at 94%",
          value: 94,
          threshold: 90,
          fired_at: new Date().toISOString(),
          fired_epoch: Date.now() / 1000,
        },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates heartbeat message", () => {
      const msg = {
        type: "heartbeat",
        timestamp: new Date().toISOString(),
        data: { uptime_seconds: 3600 },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates oom_prediction message", () => {
      const msg = {
        type: "oom_prediction",
        timestamp: new Date().toISOString(),
        data: {
          ram: {
            current_percent: 78,
            trend: "increasing",
            growth_rate_per_min: 2.1,
            confidence: 85,
            data_points: 30,
            minutes_until_full: 12,
            estimated_full_at: "~12m from now",
            severity: "warning",
          },
          gpu: [],
          data_points: 30,
          min_data_points_required: 12,
        },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates training message", () => {
      const msg = {
        type: "training",
        timestamp: new Date().toISOString(),
        data: {
          active_tasks: [],
          completed_tasks: [{ task_id: "t1", name: "fine-tune", status: "completed" }],
          stalled_tasks: [],
          total_tracked: 1,
        },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates processes message", () => {
      const msg = {
        type: "processes",
        timestamp: new Date().toISOString(),
        data: {
          summary: { total: 200, running: 5, sleeping: 195 },
          top_processes: [
            { name: "Chrome", category: "Browser", cpu_percent: 12.5, memory_mb: 800 },
          ],
          resource_breakdown: {
            cpu: [{ name: "Chrome", value: 12.5, display: "12.5%" }],
            ram: [{ name: "Chrome", value: 800, display: "800 MB" }],
          },
        },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates health message", () => {
      const msg = {
        type: "health",
        timestamp: new Date().toISOString(),
        data: {
          health_score: 85,
          rating: "good",
          components: {},
          recommendation: null,
        },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates event message", () => {
      const msg = {
        type: "event",
        timestamp: new Date().toISOString(),
        data: {
          ts: Date.now() / 1000,
          source: "alerts",
          machine: "my-laptop",
          type: "alert",
          severity: "warning",
          data: {},
          message: "CPU high",
        },
      };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("rejects invalid message type", () => {
      const msg = { type: "invalid", timestamp: new Date().toISOString(), data: {} };
      const result = agentMessageSchema.safeParse(msg);
      expect(result.success).toBe(false);
    });
  });

  describe("Dashboard messages", () => {
    it("validates subscribe message", () => {
      const msg = { type: "subscribe", agentId: "550e8400-e29b-41d4-a716-446655440000" };
      const result = dashboardMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates unsubscribe message", () => {
      const msg = { type: "unsubscribe", agentId: "550e8400-e29b-41d4-a716-446655440000" };
      const result = dashboardMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("validates training_stop message", () => {
      const msg = {
        type: "training_stop",
        agentId: "550e8400-e29b-41d4-a716-446655440000",
        taskId: "task-1",
      };
      const result = dashboardMessageSchema.safeParse(msg);
      expect(result.success).toBe(true);
    });

    it("rejects subscribe without valid UUID", () => {
      const msg = { type: "subscribe", agentId: "not-a-uuid" };
      const result = dashboardMessageSchema.safeParse(msg);
      expect(result.success).toBe(false);
    });
  });
});
