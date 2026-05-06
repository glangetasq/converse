import { z } from "zod";

export const senderTypeSchema = z.enum(["user", "contact", "unknown"]);
export const conversationSourceSchema = z.enum(["linkedin", "gmail"]);

export const importConversationRequestSchema = z.object({
  source: conversationSourceSchema,
  externalThreadId: z.string().min(1).optional(),
  rawUrl: z.string().url().optional(),
  title: z.string().min(1).optional(),
  person: z.object({
    fullName: z.string().min(1).optional(),
    email: z.string().email().optional(),
    linkedinUrl: z.string().url().optional(),
    company: z.string().min(1).optional(),
    roleTitle: z.string().min(1).optional(),
  }).optional(),
  messages: z.array(z.object({
    sourceMessageId: z.string().min(1).optional(),
    senderName: z.string().min(1).optional(),
    senderType: senderTypeSchema,
    body: z.string().min(1),
    sentAt: z.string().datetime().optional(),
    messageOrder: z.number().int().nonnegative(),
    metadata: z.record(z.unknown()).optional(),
  })).min(1),
});

export const conversationIdParamsSchema = z.object({
  id: z.string().uuid(),
});
