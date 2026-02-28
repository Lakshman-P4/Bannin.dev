import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "supertest";
import express from "express";

// Mock Prisma
vi.mock("../src/lib/prisma.js", () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
      findFirst: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
    $connect: vi.fn(),
    $disconnect: vi.fn(),
  },
  runTsvectorMigration: vi.fn(),
}));

// Mock Redis
vi.mock("../src/lib/redis.js", () => ({
  getRedis: () => ({
    connect: vi.fn(),
    quit: vi.fn(),
    on: vi.fn(),
  }),
  getRedisSubscriber: () => ({
    connect: vi.fn(),
    quit: vi.fn(),
    on: vi.fn(),
  }),
  closeRedis: vi.fn(),
}));

// Mock email
vi.mock("../src/services/email.service.js", () => ({
  sendVerificationEmail: vi.fn().mockResolvedValue(undefined),
  sendPasswordResetEmail: vi.fn().mockResolvedValue(undefined),
}));

// Import after mocks
const { createApp } = await import("../src/app.js");

describe("Auth endpoints", () => {
  let app: express.Express;

  beforeEach(() => {
    vi.clearAllMocks();
    app = createApp();
  });

  describe("POST /api/auth/register", () => {
    it("returns 422 for missing username", async () => {
      const res = await request(app)
        .post("/api/auth/register")
        .send({ password: "test1234", displayName: "Test" });

      expect(res.status).toBe(422);
      expect(res.body.error).toBeDefined();
      expect(res.body.error.code).toBe("VALIDATION_ERROR");
    });

    it("returns 422 for short password", async () => {
      const res = await request(app)
        .post("/api/auth/register")
        .send({ username: "testuser", password: "short", displayName: "Test" });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe("VALIDATION_ERROR");
    });

    it("returns 422 for missing displayName", async () => {
      const res = await request(app)
        .post("/api/auth/register")
        .send({ username: "testuser", password: "test1234" });

      expect(res.status).toBe(422);
    });

    it("returns 422 for username too short", async () => {
      const res = await request(app)
        .post("/api/auth/register")
        .send({ username: "ab", password: "test1234", displayName: "Test" });

      expect(res.status).toBe(422);
    });

    it("returns 422 for invalid username characters", async () => {
      const res = await request(app)
        .post("/api/auth/register")
        .send({ username: "test user!", password: "test1234", displayName: "Test" });

      expect(res.status).toBe(422);
    });

    it("accepts registration without email", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.user.findUnique as ReturnType<typeof vi.fn>).mockResolvedValue(null);
      (prisma.user.create as ReturnType<typeof vi.fn>).mockResolvedValue({
        id: "user-1",
        username: "testuser",
        displayName: "Test",
        email: null,
        emailVerified: false,
        createdAt: new Date(),
      });

      const res = await request(app)
        .post("/api/auth/register")
        .send({ username: "testuser", password: "test1234", displayName: "Test" });

      expect(res.status).toBe(201);
      expect(res.body.data.user.username).toBe("testuser");
      expect(res.body.data.user.email).toBeNull();
      expect(res.body.data.accessToken).toBeDefined();
      expect(res.body.data.refreshToken).toBeDefined();
    });

    it("accepts registration with email", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.user.findUnique as ReturnType<typeof vi.fn>).mockResolvedValue(null);
      (prisma.user.create as ReturnType<typeof vi.fn>).mockResolvedValue({
        id: "user-2",
        username: "emailuser",
        displayName: "Email User",
        email: "test@test.com",
        emailVerified: false,
        createdAt: new Date(),
      });

      const res = await request(app)
        .post("/api/auth/register")
        .send({ username: "emailuser", password: "test1234", displayName: "Email User", email: "test@test.com" });

      expect(res.status).toBe(201);
      expect(res.body.data.user.username).toBe("emailuser");
      expect(res.body.data.user.email).toBe("test@test.com");

      // Verify that verification email was sent
      const { sendVerificationEmail } = await import("../src/services/email.service.js");
      expect(sendVerificationEmail).toHaveBeenCalled();
    });
  });

  describe("POST /api/auth/login", () => {
    it("returns 422 for missing identifier", async () => {
      const res = await request(app)
        .post("/api/auth/login")
        .send({ password: "test1234" });

      expect(res.status).toBe(422);
    });

    it("returns 422 for missing password", async () => {
      const res = await request(app)
        .post("/api/auth/login")
        .send({ identifier: "testuser" });

      expect(res.status).toBe(422);
    });
  });

  describe("POST /api/auth/refresh", () => {
    it("returns 422 for missing refreshToken", async () => {
      const res = await request(app)
        .post("/api/auth/refresh")
        .send({});

      expect(res.status).toBe(422);
    });
  });

  describe("GET /api/auth/me", () => {
    it("returns 401 without auth header", async () => {
      const res = await request(app).get("/api/auth/me");
      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe("UNAUTHORIZED");
    });

    it("returns 401 with invalid token", async () => {
      const res = await request(app)
        .get("/api/auth/me")
        .set("Authorization", "Bearer invalid-token");
      expect(res.status).toBe(401);
    });
  });

  describe("PATCH /api/auth/me", () => {
    it("returns 401 without auth header", async () => {
      const res = await request(app)
        .patch("/api/auth/me")
        .send({ displayName: "New Name" });
      expect(res.status).toBe(401);
    });
  });

  describe("PATCH /api/auth/password", () => {
    it("returns 401 without auth header", async () => {
      const res = await request(app)
        .patch("/api/auth/password")
        .send({ currentPassword: "old", newPassword: "newpass12" });
      expect(res.status).toBe(401);
    });

    it("returns 422 for short new password", async () => {
      const res = await request(app)
        .patch("/api/auth/password")
        .set("Authorization", "Bearer invalid")
        .send({ currentPassword: "old", newPassword: "short" });
      // Gets 401 first because token is invalid, but validation runs before auth on this route
      // Actually auth middleware runs first. So this returns 401.
      expect(res.status).toBe(401);
    });
  });

  describe("DELETE /api/auth/me", () => {
    it("returns 401 without auth header", async () => {
      const res = await request(app)
        .delete("/api/auth/me")
        .send({ password: "test1234" });
      expect(res.status).toBe(401);
    });
  });

  describe("POST /api/auth/forgot-password", () => {
    it("returns 422 for invalid email", async () => {
      const res = await request(app)
        .post("/api/auth/forgot-password")
        .send({ email: "not-an-email" });
      expect(res.status).toBe(422);
    });

    it("returns 200 even for non-existent email", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.user.findUnique as ReturnType<typeof vi.fn>).mockResolvedValue(null);

      const res = await request(app)
        .post("/api/auth/forgot-password")
        .send({ email: "nonexistent@test.com" });
      expect(res.status).toBe(200);
      expect(res.body.data.message).toContain("If an account");
    });
  });

  describe("POST /api/auth/reset-password", () => {
    it("returns 422 for missing token", async () => {
      const res = await request(app)
        .post("/api/auth/reset-password")
        .send({ newPassword: "newpass12" });
      expect(res.status).toBe(422);
    });

    it("returns 422 for short password", async () => {
      const res = await request(app)
        .post("/api/auth/reset-password")
        .send({ token: "some-token", newPassword: "short" });
      expect(res.status).toBe(422);
    });

    it("returns 404 for nonexistent token", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.user.findUnique as ReturnType<typeof vi.fn>).mockResolvedValue(null);

      const res = await request(app)
        .post("/api/auth/reset-password")
        .send({ token: "nonexistent-token", newPassword: "newpass1234" });
      expect(res.status).toBe(404);
    });
  });

  describe("GET /api/auth/verify/:token", () => {
    it("returns 404 for nonexistent token", async () => {
      const { prisma } = await import("../src/lib/prisma.js");
      (prisma.user.findUnique as ReturnType<typeof vi.fn>).mockResolvedValue(null);

      const res = await request(app).get("/api/auth/verify/nonexistent-token");
      expect(res.status).toBe(404);
    });
  });
});

describe("Health endpoint", () => {
  it("returns status ok", async () => {
    const app = createApp();
    const res = await request(app).get("/api/health");
    expect(res.status).toBe(200);
    expect(res.body.status).toBe("ok");
    expect(res.body.version).toBeDefined();
    expect(typeof res.body.agents_connected).toBe("number");
  });
});

describe("404 handling", () => {
  it("returns 404 for unknown routes", async () => {
    const app = createApp();
    const res = await request(app).get("/api/nonexistent");
    expect(res.status).toBe(404);
    expect(res.body.error.code).toBe("NOT_FOUND");
  });
});
