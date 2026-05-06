import { config } from "dotenv";
import { z } from "zod";

config();

const rawEnv = { ...process.env };

if (rawEnv.NODE_ENV === "test") {
  rawEnv.DATABASE_URL ??= "postgres://postgres:postgres@localhost:5432/convo_maker_test";
  rawEnv.OPENAI_API_KEY ??= "test-openai-key";
  rawEnv.PORT ??= "3000";
}

const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  OPENAI_API_KEY: z.string().min(1),
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().positive().default(3000),
});

export type Env = z.infer<typeof envSchema>;

export const env: Env = envSchema.parse(rawEnv);
