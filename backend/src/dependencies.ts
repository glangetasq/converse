import { db } from "./db/index.js";
import { ConversationsRepository } from "./repositories/conversations.repository.js";
import { FollowupsRepository } from "./repositories/followups.repository.js";
import { MemoryRepository } from "./repositories/memory.repository.js";
import { MessagesRepository } from "./repositories/messages.repository.js";
import { PersonsRepository } from "./repositories/persons.repository.js";
import { ConversationImportService } from "./services/conversationImport.service.js";
import { FollowupService } from "./services/followup.service.js";
import { MemoryService } from "./services/memory.service.js";
import { createDbDevUserResolver } from "./middleware/devUser.js";

export function createDefaultDependencies() {
  const personsRepository = new PersonsRepository(db);
  const conversationsRepository = new ConversationsRepository(db);
  const messagesRepository = new MessagesRepository(db);
  const memoryRepository = new MemoryRepository(db);
  const followupsRepository = new FollowupsRepository(db);

  return {
    services: {
      conversations: new ConversationImportService(personsRepository, conversationsRepository, messagesRepository),
      memory: new MemoryService(memoryRepository),
      followups: new FollowupService(followupsRepository),
    },
    resolveDevUser: createDbDevUserResolver(db),
  };
}
