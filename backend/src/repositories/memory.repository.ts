import { and, desc, eq, sql } from "drizzle-orm";
import type { Db } from "../db/index.js";
import { memoryItems } from "../db/schema.js";

export type MemoryItemInput = {
  userId: string;
  personId?: string | null;
  conversationId?: string | null;
  messageId?: string | null;
  memoryType: string;
  content: string;
  contentHash: string;
  importanceScore?: number;
  confidenceScore?: number;
  source: string;
  validFrom?: Date;
  validUntil?: Date | null;
  metadata?: Record<string, unknown>;
  embedding?: number[] | null;
};

export class MemoryRepository {
  constructor(private readonly db: Db) {}

  async create(input: MemoryItemInput) {
    const [memoryItem] = await this.db.insert(memoryItems).values(input).onConflictDoNothing().returning();
    return memoryItem ?? null;
  }

  async listByPerson(userId: string, personId: string) {
    return this.db
      .select()
      .from(memoryItems)
      .where(and(eq(memoryItems.userId, userId), eq(memoryItems.personId, personId)))
      .orderBy(desc(memoryItems.importanceScore), desc(memoryItems.createdAt));
  }

  async placeholderSearch(userId: string, personId?: string) {
    const conditions = [eq(memoryItems.userId, userId)];
    if (personId) {
      conditions.push(eq(memoryItems.personId, personId));
    }

    return this.db.select().from(memoryItems).where(and(...conditions)).limit(10);
  }

  async searchByEmbedding(_userId: string, _embedding: number[], _limit: number) {
    // TODO: implement pgvector retrieval.
    // Example shape to keep nearby when wiring later:
    // orderBy(sql`${memoryItems.embedding} <-> ${embedding}`)
    void sql;
    return [];
  }
}
