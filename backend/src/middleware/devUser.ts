import type { FastifyInstance } from "fastify";
import { users } from "../db/schema.js";
import type { Db } from "../db/index.js";
import { eq } from "drizzle-orm";
import type { AppUser } from "../types/index.js";

const localDevUserEmail = "local-dev@convo-maker.test";

export type ResolveDevUser = () => Promise<AppUser>;

export function createDbDevUserResolver(db: Db): ResolveDevUser {
  return async () => {
    const [existing] = await db.select().from(users).where(eq(users.email, localDevUserEmail)).limit(1);

    if (existing) {
      return {
        id: existing.id,
        email: existing.email,
        displayName: existing.displayName,
      };
    }

    const [created] = await db.insert(users).values({
      email: localDevUserEmail,
      displayName: "Local Dev User",
    }).returning();

    return {
      id: created.id,
      email: created.email,
      displayName: created.displayName,
    };
  };
}

export async function registerDevUser(app: FastifyInstance, resolveDevUser: ResolveDevUser) {
  app.addHook("preHandler", async (request) => {
    request.user = await resolveDevUser();
  });
}
