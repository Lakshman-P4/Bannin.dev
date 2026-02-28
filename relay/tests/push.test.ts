import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "supertest";
import jwt from "jsonwebtoken";
import express from "express";

vi.mock("../src/lib/prisma.js", () => ({
  prisma: {
    user: { findUnique: vi.fn() },
    pushSubscription: {
      count: vi.fn(),
      upsert: vi.fn(),
      deleteMany: vi.fn(),
      findMany: vi.fn(),
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

vi.mock("web-push", () => ({
  default: {
    setVapidDetails: vi.fn(),
    sendNotification: vi.fn().mockResolvedValue({}),
  },
}));

const { createApp } = await import("../src/app.js");

function makeToken(): string {
  return jwt.sign(
    { id: "user-1", username: "testuser", email: "test@test.com", emailVerified: true },
    "test-jwt-secret-at-least-16-chars"
  );
}

describe("Push notification endpoints", () => {
  let app: express.Express;

  beforeEach(() => {
    vi.clearAllMocks();
    app = createApp();
  });

  describe("POST /api/notifications/push/subscribe", () => {
    it("returns 401 without auth", async () => {
      const res = await request(app)
        .post("/api/notifications/push/subscribe")
        .send({});
      expect(res.status).toBe(401);
    });

    it("returns 422 for missing subscription data", async () => {
      const token = makeToken();
      const res = await request(app)
        .post("/api/notifications/push/subscribe")
        .set("Authorization", `Bearer ${token}`)
        .send({});
      expect(res.status).toBe(422);
    });

    it("subscribes with valid data", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.pushSubscription.count as ReturnType<typeof vi.fn>).mockResolvedValue(0);
      (prisma.pushSubscription.upsert as ReturnType<typeof vi.fn>).mockResolvedValue({});

      const token = makeToken();
      const res = await request(app)
        .post("/api/notifications/push/subscribe")
        .set("Authorization", `Bearer ${token}`)
        .send({
          endpoint: "https://push.example.com/abc",
          keys: { p256dh: "key1", auth: "key2" },
        });
      expect(res.status).toBe(201);
      expect(res.body.data.message).toBe("Subscription registered");
    });
  });

  describe("DELETE /api/notifications/push/unsubscribe", () => {
    it("returns 422 for missing endpoint", async () => {
      const token = makeToken();
      const res = await request(app)
        .delete("/api/notifications/push/unsubscribe")
        .set("Authorization", `Bearer ${token}`)
        .send({});
      expect(res.status).toBe(422);
    });
  });
});
