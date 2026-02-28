import type { Request, Response, NextFunction } from "express";
import { ZodError } from "zod";
import { Prisma } from "@prisma/client";
import { logger } from "../lib/logger.js";

export function errorHandler(err: unknown, _req: Request, res: Response, _next: NextFunction): void {
  // Zod validation errors
  if (err instanceof ZodError) {
    const messages = err.errors.map((e) => `${e.path.join(".")}: ${e.message}`);
    res.status(422).json({
      error: { code: "VALIDATION_ERROR", message: messages.join("; ") },
    });
    return;
  }

  // Prisma known request errors
  if (err instanceof Prisma.PrismaClientKnownRequestError) {
    if (err.code === "P2002") {
      const target = (err.meta?.["target"] as string[] | undefined) ?? [];
      res.status(409).json({
        error: { code: "CONFLICT", message: `Unique constraint violated on: ${target.join(", ")}` },
      });
      return;
    }
    if (err.code === "P2025") {
      res.status(404).json({
        error: { code: "NOT_FOUND", message: "Record not found" },
      });
      return;
    }
    logger.warn({ err }, "Prisma request error");
    res.status(400).json({
      error: { code: "DATABASE_ERROR", message: "Invalid database request" },
    });
    return;
  }

  // JWT errors
  if (err instanceof Error && err.name === "JsonWebTokenError") {
    res.status(401).json({
      error: { code: "INVALID_TOKEN", message: "Token is invalid" },
    });
    return;
  }
  if (err instanceof Error && err.name === "TokenExpiredError") {
    res.status(401).json({
      error: { code: "TOKEN_EXPIRED", message: "Token has expired" },
    });
    return;
  }

  // Generic errors -- never leak internal messages to clients
  logger.error({ err }, "Unhandled error");
  res.status(500).json({
    error: { code: "INTERNAL_ERROR", message: "Internal server error" },
  });
}
