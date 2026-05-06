import type { FastifyInstance } from "fastify";
import type { AppServices } from "../app.js";
import {
  followupFeedbackRequestSchema,
  followupGenerationRequestSchema,
  followupIdParamsSchema,
} from "../schemas/followup.schemas.js";

export async function registerFollowupRoutes(app: FastifyInstance, options: { services: AppServices }) {
  app.post("/generate", async (request) => {
    const payload = followupGenerationRequestSchema.parse(request.body);
    return options.services.followups.generate(request.user.id, payload);
  });

  app.post("/:id/feedback", async (request, reply) => {
    const params = followupIdParamsSchema.parse(request.params);
    const payload = followupFeedbackRequestSchema.parse(request.body);
    const result = await options.services.followups.saveFeedback(request.user.id, params.id, payload);

    if (!result) {
      return reply.status(404).send({ error: "NotFound", message: "Follow-up generation not found" });
    }

    return result;
  });
}
