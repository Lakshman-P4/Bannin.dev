import type { Request, Response, NextFunction } from "express";
import * as eventsService from "../services/events.service.js";
import type { EventQuery, EventSearch } from "../schemas/events.schema.js";

export async function queryEvents(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const params = req.query as unknown as EventQuery;
    const { events, total } = await eventsService.queryEvents(req.user!.id, params);
    res.json({ data: events, meta: { total, limit: params.limit, offset: params.offset } });
  } catch (err) {
    next(err);
  }
}

export async function searchEvents(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const params = req.query as unknown as EventSearch;
    const { events, total } = await eventsService.searchEvents(req.user!.id, params.q, params.limit, params.offset);
    res.json({ data: events, meta: { total, limit: params.limit, offset: params.offset } });
  } catch (err) {
    next(err);
  }
}

export async function timeline(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const limit = Math.min(Number(req.query["limit"]) || 50, 100);
    const offset = Math.max(Number(req.query["offset"]) || 0, 0);
    const { events, total } = await eventsService.getTimeline(req.user!.id, limit, offset);
    res.json({ data: events, meta: { total, limit, offset } });
  } catch (err) {
    next(err);
  }
}
