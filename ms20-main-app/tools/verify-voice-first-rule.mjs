import assert from "node:assert/strict";
import fs from "node:fs";

const root = new URL("../../", import.meta.url);
const read = (path) => fs.readFileSync(new URL(path, root), "utf8");
const governed = [
  "README.md",
  "docs/engineering-memory/current-live-validation-state.md",
  "docs/engineering-memory/live-test-execution-discipline.md",
  "docs/engineering-memory/launch-readiness-roadmap.md",
  "ms20-main-app/README.md",
  "ms20-main-app/CURRENT_ARCHITECTURE_SNAPSHOT.md",
  "ms20-main-app/LIVE_APP_TEST_PLAN.md"
];

for (const path of governed) {
  const content = read(path);
  assert.match(content, /Voice first/iu, `${path} must preserve voice-first priority`);
  assert.match(content, /typing last/iu, `${path} must preserve typed-fallback priority`);
}

const app = read("ms20-main-app/src/app.js");
assert.match(app, /function handleCommand\(text\)[\s\S]*?routePriorityCommand\(trimmed\)/);
assert.match(app, /function handleVoiceTranscript\(text\)[\s\S]*?routePriorityCommand\(text\)/);
assert.equal((app.match(/function routePriorityCommand\(text\)/g) || []).length, 1);

const direct = read("ms20-main-app/src/services/saleDirectCommand.js");
assert.doesNotMatch(direct, /fetch\(|OpenAI|chat\.completions|responses\.create/);

console.log("VOICE_FIRST_RULE_OK priority=voice,tap,typing router=shared deterministic=true");
