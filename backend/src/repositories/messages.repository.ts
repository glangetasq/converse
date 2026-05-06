import { and, eq, inArray } from "drizzle-orm";
import type { Db } from "../db/index.js";
import { messages } from "../db/schema.js";

export type MessageInput = {
  conversationId: string;
  userId: string;
  personId?: string | null;
  sourceMessageId?: string | null;
  senderName?: string | null;
  senderType: string;
  body: string;
  sentAt?: Date | null;
  messageOrder: number;
  metadata?: Record<string, unknown>;
};

export class MessagesRepository {
  constructor(private readonly db: Db) {}

  async insertMany(inputs: MessageInput[]) {
    if (inputs.length === 0) {
      return [];
    }

    return this.db
      .insert(messages)
      .values(inputs)
      .onConflictDoNothing()
      .returning();
  }

  async findExistingSourceMessageIds(conversationId: string, sourceMessageIds: string[]) {
    if (sourceMessageIds.length === 0) {
      return new Set<string>();
    }

    const rows = await this.db
      .select({ sourceMessageId: messages.sourceMessageId })
      .from(messages)
      .where(and(eq(messages.conversationId, conversationId), inArray(messages.sourceMessageId, sourceMessageIds)));

    return new Set(rows.map((row) => row.sourceMessageId).filter((id): id is string => id !== null));
  }
}
