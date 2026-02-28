import type { Request, Response, NextFunction } from "express";
import type { ZodSchema } from "zod";

type ValidateTarget = "body" | "query" | "params";

export function validate(schema: ZodSchema, target: ValidateTarget = "body") {
  return (req: Request, res: Response, next: NextFunction): void => {
    const result = schema.safeParse(req[target]);
    if (!result.success) {
      const messages = result.error.errors.map((e) => `${e.path.join(".")}: ${e.message}`);
      res.status(422).json({
        error: { code: "VALIDATION_ERROR", message: messages.join("; ") },
      });
      return;
    }
    // Replace with parsed (and coerced/defaulted) values
    if (target === "body") {
      req.body = result.data;
    } else if (target === "query") {
      // Override query with parsed values -- use Object.assign to keep original type
      Object.assign(req.query, result.data as Record<string, unknown>);
    }
    next();
  };
}
