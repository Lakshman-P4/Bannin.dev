import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "supertest";
import jwt from "jsonwebtoken";
import express from "express";

// Mock Prisma
vi.mock("../src/lib/prisma.js", () => ({
  prisma: {
    user: { findUnique: vi.fn() },
    agent: {
      findMany: vi.fn(),
      findFirst: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      count: vi.fn(),
    },
    metricSnapshot: {
      findFirst: vi.fn(),
      findMany: vi.fn(),
      count: vi.fn(),
    },
    $connect: vi.fn(),
    $disconnect: vi.fn(),
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

function makeToken(verified = true): string {
  return jwt.sign(
    { id: "user-1", username: "testuser", email: "test@test.com", emailVerified: verified },
    "test-jwt-secret-at-least-16-chars"
  );
}

describe("Agent endpoints", () => {
  let app: express.Express;

  beforeEach(() => {
    vi.clearAllMocks();
    app = createApp();
  });

  describe("GET /api/agents", () => {
    it("returns 401 without auth", async () => {
      const res = await request(app).get("/api/agents");
      expect(res.status).toBe(401);
    });

    it("returns agent list for authenticated user (no verification required)", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.agent.findMany as ReturnType<typeof vi.fn>).mockResolvedValue([
        { id: "agent-1", name: "My Laptop", isOnline: true, createdAt: new Date() },
      ]);

      // Unverified user should still have access (no requireVerified gate)
      const token = makeToken(false);
      const res = await request(app)
        .get("/api/agents")
        .set("Authorization", `Bearer ${token}`);
      expect(res.status).toBe(200);
      expect(res.body.data).toHaveLength(1);
      expect(res.body.data[0].name).toBe("My Laptop");
    });
  });

  describe("POST /api/agents", () => {
    it("returns 422 for missing name", async () => {
      const token = makeToken(true);
      const res = await request(app)
        .post("/api/agents")
        .set("Authorization", `Bearer ${token}`)
        .send({});
      expect(res.status).toBe(422);
    });
  });
});
