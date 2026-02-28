import type { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import { getEnv } from "../config/env.js";
import type { JwtPayload } from "../types/index.js";

export function authMiddleware(req: Request, res: Response, next: NextFunction): void {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    res.status(401).json({ error: { code: "UNAUTHORIZED", message: "Missing or invalid authorization header" } });
    return;
  }

  const token = header.slice(7);
  try {
    const env = getEnv();
    const decoded = jwt.verify(token, env.JWT_SECRET) as JwtPayload;
    req.user = {
      id: decoded.id,
      username: decoded.username,
      email: decoded.email,
      emailVerified: decoded.emailVerified,
    };
    next();
  } catch {
    res.status(401).json({ error: { code: "INVALID_TOKEN", message: "Token is invalid or expired" } });
  }
}
