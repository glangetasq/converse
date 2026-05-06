import type { MemoryRepository } from "../repositories/memory.repository.js";
import type { MemoryGenerationRequest, MemorySearchRequest } from "../types/index.js";

export class MemoryService {
  constructor(private readonly memoryRepository: MemoryRepository) {}

  async listForPerson(userId: string, personId: string) {
    return this.memoryRepository.listByPerson(userId, personId);
  }

  async generate(_userId: string, _payload: MemoryGenerationRequest) {
    // TODO: implement message chunking.
    // TODO: implement structured memory extraction.
    // TODO: implement embedding storage pipeline.
    return {
      status: "placeholder",
      todo: "Implement conversation summarization and structured memory extraction.",
    };
  }

  async search(userId: string, payload: MemorySearchRequest) {
    // TODO: implement embedding query + pgvector retrieval.
    // TODO: implement hybrid reranking.
    const results = await this.memoryRepository.placeholderSearch(userId, payload.personId);

    return {
      status: "placeholder",
      todo: "Implement embedding query, pgvector search, and reranking.",
      results,
    };
  }
}
