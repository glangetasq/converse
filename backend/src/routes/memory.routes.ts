import type { FastifyInstance } from "fastify";
import type { AppServices } from "../app.js";
import {
  memoryGenerationRequestSchema,
  memorySearchRequestSchema,
} from "../schemas/memory.schemas.js";

export async function registerMemoryRoutes(app: FastifyInstance, options: { services: AppServices }) {
  app.post("/generate", async (request) => {
    const payload = memoryGenerationRequestSchema.parse(request.body);
    return options.services.memory.generate(request.user.id, payload);
  });

  app.post("/search", async (request) => {
    const payload = memorySearchRequestSchema.parse(request.body);
    return options.services.memory.search(request.user.id, payload);
  });
}
