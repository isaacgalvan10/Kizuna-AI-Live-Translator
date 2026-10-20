# 06: Church Glossary

**What to build:** Each church can define a glossary of names, recurring terms, target-language style, and Scripture translation preferences. The worker loads it and injects it into every translation request, so terms and names stay consistent through the service and across weeks.

**Blocked by:** 04 — Sentence-aware chunking + rolling context.

**Status:** done

- [x] A per-church glossary can define names, terms, style rules, and Scripture translation names.
- [x] The glossary is validated on load; invalid entries produce a clear error rather than silently degrading translations.
- [x] The glossary is injected into the prompt and used consistently for English, Korean, and Chinese.
- [x] A church without a glossary falls back safely to the default terminology.
- [x] Tests cover name usage, recurring terms, target-language style, Scripture references, and invalid glossary handling.
- [x] The Church Glossary is clearly distinguished from the project's own `GLOSSARY.md`.

## Comments

**2026-10-20** — Implemented and verified.

- Storage: new `church_glossaries` table (`ChurchGlossaryRecord`), one JSON document per church; `create_all` creates it without a database reset.
- Domain module `backend/app/church_glossary.py`: `parse_church_glossary` validates names, terms, style, and Scripture (allowed languages, non-empty values, length caps, duplicates), `load/save/delete_church_glossary` persist it, and `python -m app.church_glossary` imports or clears a document by church name. Missing storage returns `None`; invalid stored content raises `ChurchGlossaryError`.
- Prompt: `build_prompt` adds a `CHURCH GLOSSARY` section only when applicable entries exist for the active languages, covering names, recurring terms, per-language style, and Scripture translation overrides. An entry without a rendering for an active language is omitted from that request (documented in the README). No glossary leaves the prompt and built-in terminology unchanged.
- Stream: `/ws/stream` loads the glossary at handshake; invalid stored content closes with 1011 and logs only room/church IDs, never glossary text (names are personal data). Changing a glossary requires an operator reconnect.
- Docs: `backend/examples/church-glossary.example.json` and a README section; `GLOSSARY.md` now distinguishes the Church Glossary from the project glossary.
- Verification: 180 backend tests passing (was 138), `compileall` clean. New coverage includes parsing/normalization/limits/errors, DB round-trip/scoping/invalid stored content, CLI import/clear/unknown/ambiguous church, prompt injection for en/ko/zh-hans/zh-hant, omission of non-active languages, style/Scripture overrides, no-glossary defaults, worker pass-through, and handshake success/1011 with no glossary leak.
- Two-axis review fixes: public names use "Church Glossary" consistently, shared record lookup, safe logging (no exception content), deduplicated language rendering, and a duplicate-entry log-leak test.
- Scope note: the CLI (including `--clear`) is the v1 administration path; there is no admin UI.
