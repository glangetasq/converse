import { z } from "zod";

export const followupGenerationRequestSchema = z.object({
  personId: z.string().uuid().optional(),
  conversationId: z.string().uuid().optional(),
  userPrompt: z.string().optional(),
  tone: z.string().optional(),
  targetLength: z.string().optional(),
});

export const followupFeedbackRequestSchema = z.object({
  userFeedback: z.enum(["accepted", "edited", "rejected"]),
  finalSentText: z.string().optional(),
});

export const followupIdParamsSchema = z.object({
  id: z.string().uuid(),
});
