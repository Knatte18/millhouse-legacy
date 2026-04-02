# Changelog

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
