import { migrate } from "drizzle-orm/node-postgres/migrator";
import { db, pool } from "./index.js";

async function main() {
  await pool.query("CREATE EXTENSION IF NOT EXISTS vector");
  await migrate(db, { migrationsFolder: "drizzle" });
  await pool.end();
}

main().catch(async (error) => {
  console.error(error);
  await pool.end();
  process.exit(1);
});
