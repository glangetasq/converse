import { and, asc, eq } from "drizzle-orm";
import type { Db } from "../db/index.js";
import { conversations, messages } from "../db/schema.js";

export type ConversationInput = {
  userId: string;
  personId?: string | null;
  source: string;
  externalThreadId?: string | null;
  title?: string | null;
  rawUrl?: string | null;
  startedAt?: Date | null;
  lastMessageAt?: Date | null;
};

export class ConversationsRepository {
  constructor(private readonly db: Db) {}

  async findById(userId: string, id: string) {
    const [conversation] = await this.db
      .select()
      .from(conversations)
      .where(and(eq(conversations.userId, userId), eq(conversations.id, id)))
      .limit(1);

    return conversation ?? null;
  }

  async findByExternalThread(userId: string, source: string, externalThreadId: string) {
    const [conversation] = await this.db
      .select()
      .from(conversations)
      .where(
        and(
          eq(conversations.userId, userId),
          eq(conversations.source, source),
          eq(conversations.externalThreadId, externalThreadId),
        ),
      )
      .limit(1);

    return conversation ?? null;
  }

  async create(input: ConversationInput) {
    const [conversation] = await this.db.insert(conversations).values(input).returning();
    return conversation;
  }

  async updateMetadata(id: string, input: Partial<ConversationInput>) {
    const [conversation] = await this.db
      .update(conversations)
      .set({ ...input, updatedAt: new Date() })
      .where(eq(conversations.id, id))
      .returning();

    return conversation;
  }

  async getConversationWithMessages(userId: string, id: string) {
    const conversation = await this.findById(userId, id);
    if (!conversation) {
      return null;
    }

    const rows = await this.db
      .select()
      .from(messages)
      .where(eq(messages.conversationId, id))
      .orderBy(asc(messages.messageOrder), asc(messages.createdAt));

    return {
      conversation,
      messages: rows,
    };
  }
}
