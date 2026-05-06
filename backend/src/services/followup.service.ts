import type { FollowupsRepository } from "../repositories/followups.repository.js";
import type { FollowupFeedbackRequest, FollowupGenerationRequest } from "../types/index.js";

export class FollowupService {
  constructor(private readonly followupsRepository: FollowupsRepository) {}

  async generate(_userId: string, _payload: FollowupGenerationRequest) {
    // TODO: retrieve memory.
    // TODO: implement prompt assembly.
    // TODO: implement follow-up generation logic.
    // TODO: call OpenAI and save generation.
    return {
      status: "placeholder",
      todo: "Implement memory retrieval, prompt assembly, OpenAI call, and persistence.",
      generatedText: "",
    };
  }

  async saveFeedback(userId: string, id: string, payload: FollowupFeedbackRequest) {
    // TODO: implement feedback/evaluation loop.
    return this.followupsRepository.updateFeedback(userId, id, payload);
  }
}
