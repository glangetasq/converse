import { z } from "zod";

export const memoryGenerationRequestSchema = z.object({
  conversationId: z.string().uuid(),
  personId: z.string().uuid().optional(),
});

export const memorySearchRequestSchema = z.object({
  personId: z.string().uuid().optional(),
  conversationId: z.string().uuid().optional(),
  query: z.string().min(1),
  limit: z.number().int().min(1).max(50).default(10),
});

export const personMemoryParamsSchema = z.object({
  id: z.string().uuid(),
});
