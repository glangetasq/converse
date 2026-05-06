import type { ConversationsRepository } from "../repositories/conversations.repository.js";
import type { MessagesRepository } from "../repositories/messages.repository.js";
import type { PersonsRepository } from "../repositories/persons.repository.js";
import type { ImportConversationRequest } from "../types/index.js";
import { maxDate, parseOptionalDate } from "../utils/dates.js";

export class ConversationImportService {
  constructor(
    private readonly personsRepository: PersonsRepository,
    private readonly conversationsRepository: ConversationsRepository,
    private readonly messagesRepository: MessagesRepository,
  ) {}

  async importConversation(userId: string, payload: ImportConversationRequest) {
    // TODO: implement richer conversation normalization.
    // TODO: implement robust entity/person resolution beyond email/linkedin exact matches.
    const person = payload.person
      ? await this.personsRepository.findOrCreate({
          userId,
          fullName: payload.person.fullName,
          normalizedName: payload.person.fullName?.trim().toLowerCase(),
          linkedinUrl: payload.person.linkedinUrl,
          email: payload.person.email,
          company: payload.person.company,
          roleTitle: payload.person.roleTitle,
          sourceFirstSeen: payload.source,
        })
      : null;

    const sentDates = payload.messages.map((message) => parseOptionalDate(message.sentAt));
    const startedAt = sentDates.filter(Boolean).sort((a, b) => a!.getTime() - b!.getTime())[0] ?? null;
    const lastMessageAt = maxDate(sentDates);

    const existing = payload.externalThreadId
      ? await this.conversationsRepository.findByExternalThread(userId, payload.source, payload.externalThreadId)
      : null;

    const conversation = existing
      ? await this.conversationsRepository.updateMetadata(existing.id, {
          personId: person?.id ?? existing.personId,
          title: payload.title ?? existing.title,
          rawUrl: payload.rawUrl ?? existing.rawUrl,
          startedAt: existing.startedAt ?? startedAt,
          lastMessageAt: lastMessageAt ?? existing.lastMessageAt,
        })
      : await this.conversationsRepository.create({
          userId,
          personId: person?.id,
          source: payload.source,
          externalThreadId: payload.externalThreadId,
          title: payload.title,
          rawUrl: payload.rawUrl,
          startedAt,
          lastMessageAt,
        });

    const sourceMessageIds = payload.messages
      .map((message) => message.sourceMessageId)
      .filter((id): id is string => Boolean(id));
    const existingSourceMessageIds = await this.messagesRepository.findExistingSourceMessageIds(
      conversation.id,
      sourceMessageIds,
    );

    const messagesToInsert = payload.messages
      .filter((message) => !message.sourceMessageId || !existingSourceMessageIds.has(message.sourceMessageId))
      .map((message) => ({
        conversationId: conversation.id,
        userId,
        personId: person?.id,
        sourceMessageId: message.sourceMessageId,
        senderName: message.senderName,
        senderType: message.senderType,
        body: message.body,
        sentAt: parseOptionalDate(message.sentAt),
        messageOrder: message.messageOrder,
        metadata: message.metadata ?? {},
      }));

    const insertedMessages = await this.messagesRepository.insertMany(messagesToInsert);
    const stored = await this.conversationsRepository.getConversationWithMessages(userId, conversation.id);

    return {
      conversation: stored?.conversation ?? conversation,
      messages: stored?.messages ?? insertedMessages,
      importedMessageCount: insertedMessages.length,
      person,
    };
  }

  async getConversation(userId: string, id: string) {
    return this.conversationsRepository.getConversationWithMessages(userId, id);
  }
}
