import cors from "@fastify/cors";
import Fastify, { type FastifyInstance } from "fastify";
import { registerErrorHandler } from "./middleware/errorHandler.js";
import { registerDevUser, type ResolveDevUser } from "./middleware/devUser.js";
import { registerRequestLogger } from "./middleware/requestLogger.js";
import { registerHealthRoutes } from "./routes/health.routes.js";
import { registerConversationRoutes } from "./routes/conversations.routes.js";
import { registerPersonRoutes } from "./routes/persons.routes.js";
import { registerMemoryRoutes } from "./routes/memory.routes.js";
import { registerFollowupRoutes } from "./routes/followups.routes.js";
import type { AppUser } from "./types/index.js";
import type {
  FollowupFeedbackRequest,
  FollowupGenerationRequest,
  ImportConversationRequest,
  MemoryGenerationRequest,
  MemorySearchRequest,
} from "./types/index.js";

export type AppServices = {
  conversations: {
    importConversation: (userId: string, payload: ImportConversationRequest) => Promise<unknown>;
    getConversation: (userId: string, id: string) => Promise<unknown | null>;
  };
  memory: {
    listForPerson: (userId: string, personId: string) => Promise<unknown>;
    generate: (userId: string, payload: MemoryGenerationRequest) => Promise<unknown>;
    search: (userId: string, payload: MemorySearchRequest) => Promise<unknown>;
  };
  followups: {
    generate: (userId: string, payload: FollowupGenerationRequest) => Promise<unknown>;
    saveFeedback: (userId: string, id: string, payload: FollowupFeedbackRequest) => Promise<unknown | null>;
  };
};

export type CreateAppOptions = {
  services: AppServices;
  resolveDevUser?: ResolveDevUser;
  logger?: boolean;
};

const fallbackUser: AppUser = {
  id: "00000000-0000-4000-8000-000000000000",
  email: "test@convo-maker.local",
  displayName: "Test User",
};

export async function createApp(options: CreateAppOptions): Promise<FastifyInstance> {
  const app = Fastify({
    logger: options.logger ?? true,
  });

  await app.register(cors, {
    origin: true,
  });

  await registerRequestLogger(app);
  await registerDevUser(app, options.resolveDevUser ?? (async () => fallbackUser));
  await registerErrorHandler(app);

  await app.register(registerHealthRoutes);
  await app.register(registerConversationRoutes, { prefix: "/api/conversations", services: options.services });
  await app.register(registerPersonRoutes, { prefix: "/api/persons", services: options.services });
  await app.register(registerMemoryRoutes, { prefix: "/api/memory", services: options.services });
  await app.register(registerFollowupRoutes, { prefix: "/api/followups", services: options.services });

  return app;
}
