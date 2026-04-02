# Changelog

## 2026-04-03 **Weblens: Puppeteer fallback for JS-rendered pages**
- Added puppeteer-core dependency (connects to system Chrome, no bundled browser)
- New `fetchWithBrowser()` fallback in fetch-worker.mjs — launches headless Chrome when static fetch+Readability yields <100 chars
- Auto-detects Chrome/Chromium path on Windows, macOS, and Linux
- Reddit JSON path unchanged

## 2026-04-03 **Helm format-validering for .kanban.md og config.yaml**
- Shared validation rules doc at plugins/helm/doc/modules/validation.md
- .kanban.md: structural checks (single # heading, valid ## columns, ### under columns, no stray content)
- config.yaml: valid YAML, required top-level keys, optional github section validated if present
- 7 skills updated to validate after writes: helm-add, helm-start, helm-go, helm-merge, helm-abandon, helm-setup, helm-sync

## 2026-04-03 **Feedback skill — report issues from any repo**
- `/feedback` skill in conduct plugin — creates GitHub issue on Knatte18/millhouse
- Uses `gh issue create` with `feedback` label, falls back to browser if gh unavailable
- Auto-includes repo, branch, and timestamp in issue body
- Works from any repo without millhouse cloned locally

## 2026-04-02 **Helm constraints — repo-specific invariants**
- CONSTRAINTS.md in repo root — visible to humans, CC, and other tools
- Plain markdown format (headings + prose rules, no frontmatter)
- Injected in helm-go session agent setup, code reviewer prompt, and plan reviewer prompt
- Always global, always blocking, opt-in (file not created by helm-setup)
- Path resolved via `git rev-parse --show-toplevel`
- Documented in plugins/helm/doc/modules/constraints.md, recorded in decisions.md

## 2026-04-02 **Webfetch plugin — general web-to-markdown reader**
- Node.js plugin at plugins/webfetch/ with /webfetch skill
- Uses @mozilla/readability + linkedom for content extraction
- Reddit support via JSON API (no auth needed), general sites via Readability
- Parallel fetching for multiple URLs
