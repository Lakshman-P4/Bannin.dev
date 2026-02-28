import { z } from 'zod';

export const createAgentSchema = z.object({
  name: z.string().min(1, 'Agent name is required').max(100, 'Name too long'),
});

export const updateAgentSchema = z.object({
  name: z.string().min(1, 'Agent name is required').max(100, 'Name too long'),
});

export type CreateAgentFormData = z.infer<typeof createAgentSchema>;
export type UpdateAgentFormData = z.infer<typeof updateAgentSchema>;
