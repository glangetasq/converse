import type { FastifyInstance } from "fastify";
import type { AppServices } from "../app.js";
import { personMemoryParamsSchema } from "../schemas/memory.schemas.js";

export async function registerPersonRoutes(app: FastifyInstance, options: { services: AppServices }) {
  app.get("/:id/memory", async (request) => {
    const params = personMemoryParamsSchema.parse(request.params);
    const memoryItems = await options.services.memory.listForPerson(request.user.id, params.id);

    return {
      memoryItems,
    };
  });
}
