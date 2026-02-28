import rateLimit from "express-rate-limit";

export function createGlobalLimiter() {
  return rateLimit({
    windowMs: 60_000,
    max: 100,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: { code: "RATE_LIMITED", message: "Too many requests, try again later" } },
  });
}

export function createAuthLimiter() {
  return rateLimit({
    windowMs: 60_000,
    max: 5,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: { code: "RATE_LIMITED", message: "Too many auth requests, try again later" } },
  });
}

export function createResendLimiter() {
  return rateLimit({
    windowMs: 60_000,
    max: 1,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: { code: "RATE_LIMITED", message: "Verification email already sent, try again in 1 minute" } },
  });
}

// Singleton instances for production use outside of createApp()
export const globalLimiter = createGlobalLimiter();
export const authLimiter = createAuthLimiter();
export const resendLimiter = createResendLimiter();
