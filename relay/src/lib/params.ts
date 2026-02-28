import type { Request } from "express";

export function paramId(req: Request): string {
  const id = req.params["id"];
  return Array.isArray(id) ? id[0] ?? "" : id ?? "";
}
