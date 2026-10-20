# 02: Structured translation output + configurable model

**What to build:** The live translation worker returns structured JSON containing the Japanese transcript and each Active Language Channel's translation, using a configurable Gemini model. It translates only channels with listeners and makes exactly one API call per audio chunk. The prompt is built in one shared place so production, tests, and evaluation use the same instructions.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] The Gemini model is configurable without code changes; the initial default is `gemini-3.8-flash` with low thinking.
- [x] Responses are parsed from JSON matching a schema; no `[JA]` or `[EN]` tag regex remains.
- [x] One API call per chunk includes the Japanese transcript and only Active Language Channels.
- [x] Every listener of a Language Channel receives the same translation payload.
- [x] Empty channels and unknown language codes never produce an API call.
- [x] The prompt lives in a shared builder used by the worker and tests.
- [x] Tests cover English only, English plus Korean, no listeners, an unknown language, and a malformed or blocked response.
- [x] Existing feed control, guest join, and listener flows still pass.

## Comments

- Implemented `backend/app/translation_prompt.py` and `backend/app/gemini_translation.py`; the worker now uses structured JSON, a configurable model (`GEMINI_MODEL`, default `gemini-3.8-flash` with low thinking), one request per chunk, and only supported Active Language Channels.
- Moved the API key to `x-goog-api-key` and removed raw transcript/translation output logging while rewriting the request path; remaining retry and logging work stays in ticket 03.
- Verified with 22 targeted tests and the full backend suite (84 passed at the time; 109 passed at final integration). No live Gemini request was made; response handling is covered with fakes.
- Review fix pass: `docker-compose.yml` now forwards `GEMINI_MODEL`, `LOG_LEVEL`, and `KIZUNA_DEBUG_DIAGNOSTICS`, so the README settings work in Docker; the repeated language guard and finish-reason check in `gemini_translation.py` were simplified.
- All acceptance criteria are met; existing feed control, guest join, and listener flows passed in the full suite.
