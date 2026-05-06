import OpenAI from "openai";
import { env } from "../config/env.js";

const openai = new OpenAI({
  apiKey: env.OPENAI_API_KEY,
});

export async function createEmbedding(text: string): Promise<number[]> {
  const response = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: text,
  });

  return response.data[0]?.embedding ?? [];
}

export async function createChatCompletion(messages: OpenAI.Chat.ChatCompletionMessageParam[]): Promise<string> {
  const response = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages,
  });

  return response.choices[0]?.message.content ?? "";
}
