import { env } from "./config/env.js";
import { createApp } from "./app.js";
import { createDefaultDependencies } from "./dependencies.js";

const dependencies = createDefaultDependencies();
const app = await createApp({
  services: dependencies.services,
  resolveDevUser: dependencies.resolveDevUser,
  logger: env.NODE_ENV !== "test",
});

try {
  await app.listen({ port: env.PORT, host: "0.0.0.0" });
} catch (error) {
  app.log.error(error);
  process.exit(1);
}
