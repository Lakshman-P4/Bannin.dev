import { z } from "zod";

export const createAgentSchema = z.object({
  name: z.string().min(1, "Agent name is required").max(100),
});

export const updateAgentSchema = z.object({
  name: z.string().min(1, "Agent name is required").max(100),
});

export type CreateAgentInput = z.infer<typeof createAgentSchema>;
export type UpdateAgentInput = z.infer<typeof updateAgentSchema>;
