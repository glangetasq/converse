import type { FastifyError, FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import { ZodError } from "zod";

export async function registerErrorHandler(app: FastifyInstance) {
  app.setErrorHandler((error: FastifyError | ZodError, request: FastifyRequest, reply: FastifyReply) => {
    if (error instanceof ZodError) {
      return reply.status(400).send({
        error: "ValidationError",
        message: "Request validation failed",
        issues: error.issues,
      });
    }

    request.log.error(error);
    return reply.status(error.statusCode ?? 500).send({
      error: error.name ?? "InternalServerError",
      message: error.message ?? "Unexpected server error",
    });
  });
}
