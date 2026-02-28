import type { Request, Response, NextFunction } from "express";
import * as agentsService from "../services/agents.service.js";
import { paramId } from "../lib/params.js";
import type { CreateAgentInput, UpdateAgentInput } from "../schemas/agents.schema.js";

export async function list(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agents = await agentsService.listAgents(req.user!.id);
    res.json({ data: agents });
  } catch (err) {
    next(err);
  }
}

export async function create(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as CreateAgentInput;
    const result = await agentsService.createAgent(req.user!.id, input);
    res.status(201).json({
      data: {
        ...result.agent,
        apiKey: result.apiKey,
      },
    });
  } catch (err) {
    if (err instanceof agentsService.LimitError) {
      res.status(400).json({ error: { code: "LIMIT_EXCEEDED", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function get(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    if (!agentId) {
      res.status(400).json({ error: { code: "BAD_REQUEST", message: "Agent ID required" } });
      return;
    }
    const agent = await agentsService.getAgent(req.user!.id, agentId);
    res.json({ data: agent });
  } catch (err) {
    if (err instanceof agentsService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function update(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    if (!agentId) {
      res.status(400).json({ error: { code: "BAD_REQUEST", message: "Agent ID required" } });
      return;
    }
    const input = req.body as UpdateAgentInput;
    const agent = await agentsService.updateAgent(req.user!.id, agentId, input);
    res.json({ data: agent });
  } catch (err) {
    if (err instanceof agentsService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function remove(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    if (!agentId) {
      res.status(400).json({ error: { code: "BAD_REQUEST", message: "Agent ID required" } });
      return;
    }
    await agentsService.deleteAgent(req.user!.id, agentId);
    res.json({ data: { message: "Agent deleted" } });
  } catch (err) {
    if (err instanceof agentsService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function regenerateKey(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const agentId = paramId(req);
    if (!agentId) {
      res.status(400).json({ error: { code: "BAD_REQUEST", message: "Agent ID required" } });
      return;
    }
    const result = await agentsService.regenerateKey(req.user!.id, agentId);
    res.json({ data: { apiKey: result.apiKey } });
  } catch (err) {
    if (err instanceof agentsService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}
