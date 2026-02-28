import { beforeAll, afterAll } from "vitest";

// Set test environment variables before any imports
process.env["NODE_ENV"] = "test";
process.env["JWT_SECRET"] = "test-jwt-secret-at-least-16-chars";
process.env["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-16";
process.env["DATABASE_URL"] = process.env["DATABASE_URL"] ?? "postgresql://postgres:postgres@localhost:5432/bannin_relay_test";
process.env["REDIS_URL"] = process.env["REDIS_URL"] ?? "redis://localhost:6379/1";
process.env["ALLOWED_ORIGINS"] = "http://localhost:3000";

beforeAll(() => {
  // Tests may run without actual DB -- individual tests handle mocking
});

afterAll(() => {
  // Cleanup
});
