---
name: weblens
description: "Fetch blocked/restricted web pages and answer questions about their content"
argument-hint: "<url> [url2...] [question]"
---

Fetch web pages that Claude Code's built-in WebFetch cannot read (Reddit, paywalled sites, bot-blocked sites). Uses a real browser user-agent and Readability extraction.

Only use this skill when the built-in WebFetch fails or returns unusable content.

## Steps

1. Create `_millhouse/scratch/` if it doesn't exist.

2. Fetch the URL(s):
   ```bash
   bash ${CLAUDE_SKILL_DIR}/../../scripts/run.sh <url1> [url2...] > _millhouse/scratch/weblens-output.md
   ```

3. Read `_millhouse/scratch/weblens-output.md`.

4. Answer the user's question based on the content. If no question was provided, give a brief summary (3-5 sentences per source).

5. Do NOT show the raw fetched content to the user. Only show your answer/summary.
