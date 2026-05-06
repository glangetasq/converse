import { and, eq } from "drizzle-orm";
import type { Db } from "../db/index.js";
import { followupGenerations } from "../db/schema.js";

export type FollowupGenerationInput = {
  userId: string;
  personId?: string | null;
  conversationId?: string | null;
  userPrompt?: string | null;
  tone?: string | null;
  targetLength?: string | null;
  retrievedMemoryIds?: string[];
  modelName?: string | null;
  generatedText: string;
  metadata?: Record<string, unknown>;
};

export class FollowupsRepository {
  constructor(private readonly db: Db) {}

  async create(input: FollowupGenerationInput) {
    const [generation] = await this.db.insert(followupGenerations).values(input).returning();
    return generation;
  }

  async updateFeedback(userId: string, id: string, input: { userFeedback: string; finalSentText?: string }) {
    const [generation] = await this.db
      .update(followupGenerations)
      .set({
        userFeedback: input.userFeedback,
        finalSentText: input.finalSentText,
      })
      .where(and(eq(followupGenerations.userId, userId), eq(followupGenerations.id, id)))
      .returning();

    return generation ?? null;
  }
}
