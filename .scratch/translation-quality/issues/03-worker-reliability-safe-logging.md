# 03: Worker reliability + safe logging

**What to build:** The translation worker survives transient Gemini failures without losing or duplicating sermon audio, keeps credentials and sermon content out of logs, and records token usage and estimated cost for every request.

**Blocked by:** 02 — Structured translation output + configurable model.

**Status:** ready-for-agent

- [x] 429, 5xx, and timeout responses retry with bounded exponential backoff and jitter; permanent failures do not hot-loop.
- [x] A failed request never re-sends audio that already reached listeners, and a retry never duplicates a translated line.
- [x] Audio from a previous loop iteration can never be re-queued by an exception in the current iteration.
- [x] The API key is sent in a request header, never in the URL.
- [x] Sermon text is not logged by default; diagnostic logging is opt-in and redacted.
- [x] Every request sets an output-token limit and handles blocked, max-token, and recitation finish reasons.
- [x] Every response records input, output, and thinking token usage and converts it to an estimated cost.
- [x] Tests cover retry, duplicate prevention, and blocked or empty responses.

## Comments

- **Implemented:** `GeminiTranslator` retries 408/429/500/502/503/504/507/508 and transport failures up to 3 attempts, with 0.5s/1.0s exponential backoff plus up to 25% jitter; the base delay is capped at 4s. 501/505 are permanent and fail immediately. Each attempt has a 5s timeout and the whole retry loop has an 8s budget, bounding a flush to the spec's failure threshold.
- **Usage/cost:** every request sets `maxOutputTokens=2048`; `TranslationResult.usage` now carries input, output, thinking, and total tokens plus `estimated_cost_usd`. Pricing covers 3.8 Flash ($0.75/$3.75 per M), 3.5 Flash-Lite ($0.30/$2.50), and 2.5 Flash ($1.00/$2.50); thinking tokens are billed at the output rate. Usage is parsed and logged before response validation, so blocked, max-token, and malformed responses still record consumed tokens.
- **Finish reasons:** blocked, recitation, and max-token handling from ticket 02 remains; the output cap is now explicit.
- **Duplicate prevention:** extracted `GeminiWorker._flush_once()`. Audio is removed from the buffer before the request and is never requeued after removal, so a translation or broadcast failure cannot replay a line. A failed channel may miss that line instead of duplicating it.
- **Safe logging:** default logs contain only room ID, byte/char counts, language codes, and usage/cost metadata — no sermon text or API key. `KIZUNA_DEBUG_DIAGNOSTICS=true` adds audio byte and non-zero counts only, still no transcript content. `main.py` configures `LOG_LEVEL` (default `INFO`) so usage logs are emitted.
- **API key:** already sent only in `x-goog-api-key`; verified in ticket 02.
- **Verification:** 57 targeted tests (`test_translation.py`, `test_gemini_worker.py`, `test_socket_manager.py`, `test_seed_church.py`), 109 full backend tests passed, `compileall` passed, and `docker compose config --quiet` is clean. New tests cover 429 retry, timeout retry, max attempts, non-retryable status, usage/cost, usage on blocked responses, missing usage, empty responses, overall retry budget, no duplicate after broadcast failure, drop-on-translation-error, deadline handling, unsupported-language clearing, minimum buffer, default log redaction, opt-in diagnostics, and transport-error handling.
- **Remaining:** pricing uses 2026 intro rates; the 2027 increase is not encoded. The 8s overall budget bounds a single flush; measure p95 in ticket 08. No live Gemini request was made.
- All acceptance criteria are met.
