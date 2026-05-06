import {
  index,
  integer,
  jsonb,
  pgTable,
  real,
  text,
  timestamp,
  uniqueIndex,
  uuid,
  vector,
} from "drizzle-orm/pg-core";

const timestamps = {
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
};

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").unique(),
  displayName: text("display_name"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const persons = pgTable(
  "persons",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    fullName: text("full_name"),
    normalizedName: text("normalized_name"),
    linkedinUrl: text("linkedin_url"),
    email: text("email"),
    company: text("company"),
    roleTitle: text("role_title"),
    sourceFirstSeen: text("source_first_seen"),
    ...timestamps,
  },
  (table) => ({
    userEmailIdx: index("persons_user_email_idx").on(table.userId, table.email),
    userLinkedinIdx: index("persons_user_linkedin_idx").on(table.userId, table.linkedinUrl),
  }),
);

export const conversations = pgTable(
  "conversations",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    personId: uuid("person_id").references(() => persons.id, { onDelete: "set null" }),
    source: text("source").notNull(),
    externalThreadId: text("external_thread_id"),
    title: text("title"),
    rawUrl: text("raw_url"),
    startedAt: timestamp("started_at", { withTimezone: true }),
    lastMessageAt: timestamp("last_message_at", { withTimezone: true }),
    ...timestamps,
  },
  (table) => ({
    sourceThreadIdx: uniqueIndex("conversations_user_source_thread_idx").on(
      table.userId,
      table.source,
      table.externalThreadId,
    ),
  }),
);

export const messages = pgTable(
  "messages",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    conversationId: uuid("conversation_id").notNull().references(() => conversations.id, { onDelete: "cascade" }),
    userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    personId: uuid("person_id").references(() => persons.id, { onDelete: "set null" }),
    sourceMessageId: text("source_message_id"),
    senderName: text("sender_name"),
    senderType: text("sender_type").notNull().default("unknown"),
    body: text("body").notNull(),
    sentAt: timestamp("sent_at", { withTimezone: true }),
    messageOrder: integer("message_order").notNull(),
    metadata: jsonb("metadata").$type<Record<string, unknown>>().notNull().default({}),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    conversationOrderIdx: index("messages_conversation_order_idx").on(table.conversationId, table.messageOrder),
    conversationSourceMessageIdx: uniqueIndex("messages_conversation_source_message_idx").on(
      table.conversationId,
      table.sourceMessageId,
    ),
  }),
);

export const memoryItems = pgTable(
  "memory_items",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    personId: uuid("person_id").references(() => persons.id, { onDelete: "set null" }),
    conversationId: uuid("conversation_id").references(() => conversations.id, { onDelete: "set null" }),
    messageId: uuid("message_id").references(() => messages.id, { onDelete: "set null" }),
    memoryType: text("memory_type").notNull(),
    content: text("content").notNull(),
    contentHash: text("content_hash").notNull(),
    importanceScore: real("importance_score").notNull().default(0.5),
    confidenceScore: real("confidence_score").notNull().default(1),
    source: text("source").notNull(),
    validFrom: timestamp("valid_from", { withTimezone: true }).notNull().defaultNow(),
    validUntil: timestamp("valid_until", { withTimezone: true }),
    metadata: jsonb("metadata").$type<Record<string, unknown>>().notNull().default({}),
    embedding: vector("embedding", { dimensions: 1536 }),
    ...timestamps,
  },
  (table) => ({
    userPersonIdx: index("memory_items_user_person_idx").on(table.userId, table.personId),
    contentHashIdx: uniqueIndex("memory_items_user_content_hash_idx").on(table.userId, table.contentHash),
  }),
);

export const followupGenerations = pgTable("followup_generations", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
  personId: uuid("person_id").references(() => persons.id, { onDelete: "set null" }),
  conversationId: uuid("conversation_id").references(() => conversations.id, { onDelete: "set null" }),
  userPrompt: text("user_prompt"),
  tone: text("tone"),
  targetLength: text("target_length"),
  retrievedMemoryIds: jsonb("retrieved_memory_ids").$type<string[]>().notNull().default([]),
  modelName: text("model_name"),
  generatedText: text("generated_text").notNull(),
  userFeedback: text("user_feedback"),
  finalSentText: text("final_sent_text"),
  metadata: jsonb("metadata").$type<Record<string, unknown>>().notNull().default({}),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export type User = typeof users.$inferSelect;
export type Person = typeof persons.$inferSelect;
export type Conversation = typeof conversations.$inferSelect;
export type Message = typeof messages.$inferSelect;
export type MemoryItem = typeof memoryItems.$inferSelect;
export type FollowupGeneration = typeof followupGenerations.$inferSelect;
