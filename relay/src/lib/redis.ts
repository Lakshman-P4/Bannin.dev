import Redis from "ioredis";
import { logger } from "./logger.js";

let _redis: Redis | null = null;
let _sub: Redis | null = null;

export function getRedis(): Redis {
  if (_redis) return _redis;
  const url = process.env["REDIS_URL"] ?? "redis://localhost:6379";
  _redis = new Redis(url, {
    maxRetriesPerRequest: 3,
    retryStrategy(times: number): number | null {
      if (times > 10) return null;
      return Math.min(times * 200, 5000);
    },
    lazyConnect: true,
  });
  _redis.on("error", (err) => {
    logger.warn({ err }, "Redis connection error");
  });
  _redis.on("connect", () => {
    logger.info("Redis connected");
  });
  return _redis;
}

export function getRedisSubscriber(): Redis {
  if (_sub) return _sub;
  const url = process.env["REDIS_URL"] ?? "redis://localhost:6379";
  _sub = new Redis(url, {
    maxRetriesPerRequest: 3,
    retryStrategy(times: number): number | null {
      if (times > 10) return null;
      return Math.min(times * 200, 5000);
    },
    lazyConnect: true,
  });
  _sub.on("error", (err) => {
    logger.warn({ err }, "Redis subscriber connection error");
  });
  return _sub;
}

export async function closeRedis(): Promise<void> {
  if (_redis) {
    await _redis.quit().catch(() => {});
    _redis = null;
  }
  if (_sub) {
    await _sub.quit().catch(() => {});
    _sub = null;
  }
}
