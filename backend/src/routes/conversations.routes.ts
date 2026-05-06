import type { FastifyInstance } from "fastify";
import type { AppServices } from "../app.js";
import {
  conversationIdParamsSchema,
  importConversationRequestSchema,
} from "../schemas/conversation.schemas.js";

export async function registerConversationRoutes(app: FastifyInstance, options: { services: AppServices }) {
  app.post("/import", async (request, reply) => {
    const payload = importConversationRequestSchema.parse(request.body);
    const result = await options.services.conversations.importConversation(request.user.id, payload);
    return reply.status(201).send(result);
  });

  app.get("/:id", async (request, reply) => {
    const params = conversationIdParamsSchema.parse(request.params);
    const result = await options.services.conversations.getConversation(request.user.id, params.id);

    if (!result) {
      return reply.status(404).send({ error: "NotFound", message: "Conversation not found" });
    }

    return result;
  });
}
