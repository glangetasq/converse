# End-to-end harness

Drives the real extension in headless Chromium against the mini-LinkedIn fixture
(`dev/mini-linkedin/`), a second backend instance on port 3001, and a fake LLM
provider (`fake_provider.py`, port 8990) that mimics `/v1/messages`, `/v1/responses`
and `/v1/embeddings` — so the full generate path runs without API keys or cost.

```sh
cd dev/e2e
npm init -y && npm i playwright@1.61.1   # one-time; artifacts are gitignored
node e2e.js                              # needs Postgres up (docker compose)
```

Screenshots land in `dev/e2e/shots/`. The harness opens `popup.html` as a regular
tab (the side panel itself is not scriptable); `popup.js` detects that case and
targets the most recent web tab.

It writes fixture rows (person "Maya Lindqvist", eval examples, generations) to the
dev database — clean them after a run:

```sql
DELETE FROM eval_examples WHERE recipient_id IN (SELECT id FROM persons WHERE full_name='Maya Lindqvist');
DELETE FROM followup_generations WHERE person_id IN (SELECT id FROM persons WHERE full_name='Maya Lindqvist');
DELETE FROM source_documents WHERE person_id IN (SELECT id FROM persons WHERE full_name='Maya Lindqvist');
DELETE FROM persons WHERE full_name='Maya Lindqvist';
```
