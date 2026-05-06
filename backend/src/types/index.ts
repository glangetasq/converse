import type { FastifyRequest } from "fastify";
import type { z } from "zod";
import type {
  followupFeedbackRequestSchema,
  followupGenerationRequestSchema,
} from "../schemas/followup.schemas.js";
import type {
  importConversationRequestSchema,
} from "../schemas/conversation.schemas.js";
import type {
  memoryGenerationRequestSchema,
  memorySearchRequestSchema,
} from "../schemas/memory.schemas.js";

export type AppUser = {
  id: string;
  email: string | null;
  displayName: string | null;
};

export type RequestWithUser = FastifyRequest & {
  user: AppUser;
};

export type ImportConversationRequest = z.infer<typeof importConversationRequestSchema>;
export type MemoryGenerationRequest = z.infer<typeof memoryGenerationRequestSchema>;
export type MemorySearchRequest = z.infer<typeof memorySearchRequestSchema>;
export type FollowupGenerationRequest = z.infer<typeof followupGenerationRequestSchema>;
export type FollowupFeedbackRequest = z.infer<typeof followupFeedbackRequestSchema>;

declare module "fastify" {
  interface FastifyRequest {
    user: AppUser;
  }
}
