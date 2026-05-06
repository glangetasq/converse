import { and, eq, or } from "drizzle-orm";
import type { Db } from "../db/index.js";
import { persons } from "../db/schema.js";

export type PersonInput = {
  userId: string;
  fullName?: string;
  normalizedName?: string;
  linkedinUrl?: string;
  email?: string;
  company?: string;
  roleTitle?: string;
  sourceFirstSeen?: string;
};

export class PersonsRepository {
  constructor(private readonly db: Db) {}

  async findById(userId: string, id: string) {
    const [person] = await this.db.select().from(persons).where(and(eq(persons.userId, userId), eq(persons.id, id))).limit(1);
    return person ?? null;
  }

  async findLikelyExisting(input: Pick<PersonInput, "userId" | "email" | "linkedinUrl">) {
    const conditions = [];
    if (input.email) {
      conditions.push(eq(persons.email, input.email));
    }
    if (input.linkedinUrl) {
      conditions.push(eq(persons.linkedinUrl, input.linkedinUrl));
    }

    if (conditions.length === 0) {
      return null;
    }

    const [person] = await this.db
      .select()
      .from(persons)
      .where(and(eq(persons.userId, input.userId), or(...conditions)))
      .limit(1);

    return person ?? null;
  }

  async create(input: PersonInput) {
    const [person] = await this.db.insert(persons).values(input).returning();
    return person;
  }

  async findOrCreate(input: PersonInput) {
    const existing = await this.findLikelyExisting(input);
    if (existing) {
      return existing;
    }

    return this.create(input);
  }
}
