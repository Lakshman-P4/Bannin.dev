import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "supertest";
import jwt from "jsonwebtoken";
import express from "express";

vi.mock("../src/lib/prisma.js", () => ({
  prisma: {
    user: { findUnique: vi.fn() },
    agent: { findMany: vi.fn(), findFirst: vi.fn() },
    event: { findMany: vi.fn(), count: vi.fn() },
    $connect: vi.fn(),
    $disconnect: vi.fn(),
    $queryRaw: vi.fn(),
  },
  runTsvectorMigration: vi.fn(),
}));

vi.mock("../src/lib/redis.js", () => ({
  getRedis: () => ({ connect: vi.fn(), quit: vi.fn(), on: vi.fn() }),
  getRedisSubscriber: () => ({ connect: vi.fn(), quit: vi.fn(), on: vi.fn() }),
  closeRedis: vi.fn(),
}));

vi.mock("../src/services/email.service.js", () => ({
  sendVerificationEmail: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
}));

const { createApp } = await import("../src/app.js");

function makeToken(): string {
  return jwt.sign(
    { id: "user-1", username: "testuser", email: "test@test.com", emailVerified: true },
    "test-jwt-secret-at-least-16-chars"
  );
}

describe("Events endpoints", () => {
  let app: express.Express;

  beforeEach(() => {
    vi.clearAllMocks();
    app = createApp();
  });

  describe("GET /api/events", () => {
    it("returns 401 without auth", async () => {
      const res = await request(app).get("/api/events");
      expect(res.status).toBe(401);
    });

    it("returns events for authenticated user", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.agent.findMany as ReturnType<typeof vi.fn>).mockResolvedValue([
        { id: "agent-1" },
      ]);
      (prisma.event.findMany as ReturnType<typeof vi.fn>).mockResolvedValue([
        { id: "ev-1", type: "alert", message: "RAM high", timestamp: new Date() },
      ]);
      (prisma.event.count as ReturnType<typeof vi.fn>).mockResolvedValue(1);

      const token = makeToken();
      const res = await request(app)
        .get("/api/events")
        .set("Authorization", `Bearer ${token}`);
      expect(res.status).toBe(200);
      expect(res.body.data).toHaveLength(1);
      expect(res.body.meta).toBeDefined();
      expect(res.body.meta.total).toBe(1);
    });
  });

  describe("GET /api/events/timeline", () => {
    it("returns events newest-first", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.agent.findMany as ReturnType<typeof vi.fn>).mockResolvedValue([{ id: "agent-1" }]);
      (prisma.event.findMany as ReturnType<typeof vi.fn>).mockResolvedValue([]);
      (prisma.event.count as ReturnType<typeof vi.fn>).mockResolvedValue(0);

      const token = makeToken();
      const res = await request(app)
        .get("/api/events/timeline")
        .set("Authorization", `Bearer ${token}`);
      expect(res.status).toBe(200);
      expect(res.body.data).toEqual([]);
      expect(res.body.meta.total).toBe(0);
    });
  });
});
