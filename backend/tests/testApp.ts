import type { AppServices } from "../src/app.js";
import { createApp } from "../src/app.js";
import type {
  FollowupFeedbackRequest,
  FollowupGenerationRequest,
  ImportConversationRequest,
  MemoryGenerationRequest,
  MemorySearchRequest,
} from "../src/types/index.js";

const testUser = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "test@example.com",
  displayName: "Test User",
};

export function makeTestServices(): AppServices {
  const conversations = new Map<string, { conversation: Record<string, unknown>; messages: Record<string, unknown>[] }>();

  return {
    conversations: {
      async importConversation(userId: string, payload: ImportConversationRequest) {
        const id = payload.externalThreadId ?? "22222222-2222-4222-8222-222222222222";
        const conversation = {
          id,
          userId,
          source: payload.source,
          externalThreadId: payload.externalThreadId,
          title: payload.title,
        };
        const messages = payload.messages.map((message, index) => ({
          id: `message-${index}`,
          conversationId: id,
          ...message,
        }));

        conversations.set(id, { conversation, messages });

        return {
          conversation,
          messages,
          importedMessageCount: messages.length,
        };
      },
      async getConversation(_userId: string, id: string) {
        return conversations.get(id) ?? null;
      },
    },
    memory: {
      async listForPerson(_userId: string, personId: string) {
        return [{ id: "memory-1", personId, content: "Existing memory" }];
      },
      async generate(_userId: string, _payload: MemoryGenerationRequest) {
        return { status: "placeholder" };
      },
      async search(_userId: string, _payload: MemorySearchRequest) {
        return { status: "placeholder", results: [] };
      },
    },
    followups: {
      async generate(_userId: string, _payload: FollowupGenerationRequest) {
        return { status: "placeholder", generatedText: "" };
      },
      async saveFeedback(_userId: string, id: string, payload: FollowupFeedbackRequest) {
        return { id, ...payload };
      },
    },
  };
}

export async function makeTestApp() {
  return createApp({
    services: makeTestServices(),
    resolveDevUser: async () => testUser,
    logger: false,
  });
}
