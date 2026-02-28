import { z } from "zod";

const envSchema = z.object({
  DATABASE_URL: z.string().min(1),
  REDIS_URL: z.string().default("redis://localhost:6379"),
  JWT_SECRET: z.string().min(16),
  JWT_REFRESH_SECRET: z.string().min(16),
  JWT_EXPIRES_IN: z.string().default("15m"),
  JWT_REFRESH_EXPIRES_IN: z.string().default("7d"),
  PORT: z.coerce.number().default(3001),
  ALLOWED_ORIGINS: z.string().default("http://localhost:3000"),
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  BREVO_API_KEY: z.string().default(""),
  EMAIL_FROM_NAME: z.string().default("Bannin"),
  EMAIL_FROM_ADDRESS: z.string().default(""),
  APP_URL: z.string().default("http://localhost:3000"),
  VAPID_PUBLIC_KEY: z.string().default(""),
  VAPID_PRIVATE_KEY: z.string().default(""),
  VAPID_EMAIL: z.string().default(""),
});

export type Env = z.infer<typeof envSchema>;

let _env: Env | null = null;

export function getEnv(): Env {
  if (_env) return _env;
  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    const formatted = result.error.flatten().fieldErrors;
    const missing = Object.entries(formatted)
      .map(([key, errors]) => `  ${key}: ${(errors ?? []).join(", ")}`)
      .join("\n");
    throw new Error(`Invalid environment variables:\n${missing}`);
  }
  _env = result.data;
  return _env;
}
