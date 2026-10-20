# 06: Church Glossary

**What to build:** Each church can define a glossary of names, recurring terms, target-language style, and Scripture translation preferences. The worker loads it and injects it into every translation request, so terms and names stay consistent through the service and across weeks.

**Blocked by:** 04 — Sentence-aware chunking + rolling context.

**Status:** ready-for-agent

- [ ] A per-church glossary can define names, terms, style rules, and Scripture translation names.
- [ ] The glossary is validated on load; invalid entries produce a clear error rather than silently degrading translations.
- [ ] The glossary is injected into the prompt and used consistently for English, Korean, and Chinese.
- [ ] A church without a glossary falls back safely to the default terminology.
- [ ] Tests cover name usage, recurring terms, target-language style, Scripture references, and invalid glossary handling.
- [ ] The Church Glossary is clearly distinguished from the project's own `GLOSSARY.md`.
