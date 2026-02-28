import { PrismaClient } from "@prisma/client";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { logger } from "./logger.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log:
      process.env["NODE_ENV"] === "development"
        ? [{ emit: "event", level: "warn" }]
        : [],
  });

if (process.env["NODE_ENV"] !== "production") {
  globalForPrisma.prisma = prisma;
}

export async function runTsvectorMigration(): Promise<void> {
  try {
    const sqlPath = join(__dirname, "..", "..", "prisma", "migrations", "add_tsvector.sql");
    const sql = readFileSync(sqlPath, "utf-8");
    await prisma.$executeRawUnsafe(sql);
    logger.info("tsvector migration applied successfully");
  } catch (error) {
    // Table might not exist yet on first run, or migration already applied
    logger.warn({ error }, "tsvector migration skipped or already applied");
  }
}
