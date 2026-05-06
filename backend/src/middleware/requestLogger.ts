import type { FastifyInstance } from "fastify";

export async function registerRequestLogger(app: FastifyInstance) {
  app.addHook("onRequest", async (request) => {
    request.log.info({ method: request.method, url: request.url }, "incoming request");
  });
}
