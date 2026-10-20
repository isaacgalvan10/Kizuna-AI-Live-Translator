# Translation Quality & Production Deployment

## Summary

Make the church live translator accurate, quick, and cost-efficient for one Japanese church, then deploy it as a stable web app that a few more churches can use. The API target is roughly $1–2 per church per month; the overall recurring target is about $10 per month (soft ceiling).

## Goals

- Japanese sermon audio to English, Korean, and Chinese translations that are faithful first, natural second, and verse-accurate for direct Bible quotes.
- End-to-end delay of roughly 3–5 seconds; more than 8 seconds is a failure.
- One Gemini API call per audio chunk for all Active Language Channels. Empty channels are never translated. Every listener of a channel receives the same translation.
- A deployment the church can use from browsers: operator console on the mixer laptop, guests on phones via a permanent QR code. No app installs.
- A repeatable evaluation harness so model and prompt changes are judged against real sermon audio, not intuition.
- Operational cost visibility and a documented deployment and runbook.

## Non-goals

- Native mobile apps.
- Server-side TTS; browser speech synthesis remains the voice.
- Automatic worship or music detection; the operator pauses the feed.
- An admin UI for onboarding churches; a CLI is the v1 path.
- Horizontal scaling or multiple backend instances.
- Persisting Transcript Timeline history across backend restarts.
- Transcribing when no listeners are connected.
- Fine-tuning a model.

## Domain Vocabulary

The canonical project glossary is `GLOSSARY.md`. This effort adds:

- **Language Channel** — one language's stream within a Live Feed; all listeners of that language share it.
- **Active Language Channel** — a Language Channel with at least one Listener.
- **Transcript Timeline** — the ordered Japanese transcript of the current Live Feed, shared across channels.
- **Backfill** — translating recent Transcript Timeline lines into a newly active Language Channel.
- **Church Glossary** — a church's names, recurring terms, style rules, and Scripture translation preferences.

## Locked Decisions

### Translation

- **Model:** configurable. Default `gemini-3.8-flash` with `thinking_level: "low"`. Compare against `gemini-3.5-flash-lite` on real audio and set the winner as the default.
- **Output:** structured JSON containing the Japanese transcript and each active language's translation. No tag regex parsing.
- **Scope:** one API call per chunk; only Active Language Channels; the same translation payload goes to every listener of a channel.
- **Prompt:** one shared builder used by production and evaluation. It includes:
  - Rolling context from the previous 1–2 transcript lines.
  - Church Glossary names, terms, and style.
  - Target-language rules: Korean formal polite style; Simplified Chinese Protestant terminology.
  - Scripture policy: 新共同訳 source; ESV (English), 개역개정 (Korean), 和合本 (Chinese) for direct quotes.
  - Fragment handling: translate what was said, never complete an unfinished thought or invent content.
  - Cleaned Japanese transcript: remove fillers and non-meaningful affirmations.
- **Safety:** paid Gemini tier; no sermon text in logs by default; API key in a header, never a URL.

### Audio

- Input is 16 kHz, 16-bit mono PCM from the operator browser.
- The operator can choose the input device. Laptop microphone mode keeps browser DSP on; mixer or line mode disables echo cancellation, noise suppression, and AGC.
- Chunking is sentence or silence aware with a small overlap and deduplication, not a fixed 3-second timer.
- Retries never duplicate audio or re-broadcast a line that already reached listeners.

### History

- A shared Japanese Transcript Timeline exists for the current Live Feed.
- Each Language Channel has its own translation history.
- A listener joining an existing channel receives that channel's history.
- A listener joining a new or empty channel receives the recent Japanese transcript plus a Backfill of the last 3 minutes (maximum 25 lines) in one batch call.
- History clears on a fresh Start, survives Pause/Resume and reconnects, and begins at the first listener. Zero listeners means no API calls.

### Evaluation

- Golden set: 20–30 minutes of real sermon audio from the same preacher, 3–5 clips, including a Scripture reading, names, English code-switching, and fast or quiet speech.
- YouTube auto-captions are a draft for the Japanese references and are corrected manually.
- English is reviewed by the user. Korean and Chinese use a Gemini LLM judge with the same rubric, blind labels, and a later native spot-check.
- Metrics: Japanese CER, faithfulness, fluency, terminology consistency, Scripture accuracy, p50/p95 latency, and cost from token usage.

### Deployment and Cost

- Tokyo VPS, 2 vCPU / 2 GB RAM, running Docker Compose: backend, Postgres, Caddy with HTTPS.
- A cheap, stable domain for the printed QR code. No changing tunnel URL.
- Onboarding uses a server-side CLI, not the public dev seed endpoint.
- API cost is roughly $1–2 per church per month. One church totals about $7–9 per month; three churches about $10–12 per month. The $10 figure is a target, not a hard ceiling.
- A Google billing alert is configured at the agreed threshold.

## Assumptions

- One backend process; WebSocket, worker, and history state are in memory.
- A backend restart loses the current service's Transcript Timeline; listeners can reconnect and continue.
- Browser TTS remains the only spoken translation.
- The church laptop and mixer remain the audio source and are a single point of failure for a service.
- Church names are not unique in the current schema; the onboarding CLI rejects ambiguous names. A unique slug is future work.

## Risks

- VPS or church laptop failure during a service.
- Gemini model pricing or availability changes; 3.8 Flash introductory pricing doubles on 2027-01-01.
- LLM judge bias without native Korean or Chinese review.
- In-memory history lost on restart.
- Church name ambiguity during onboarding.
- Printed QR codes depend on a stable domain.

## Verification

- Each ticket has acceptance criteria and automated tests.
- The evaluation harness compares models and prompts on the golden set.
- An end-to-end phone test on cellular confirms QR, language picker, and live text.
- A restore-from-backup check confirms operational recovery.

## Tickets

| # | Ticket | Blocked by |
|---|---|---|
| 01 | Church onboarding CLI | None |
| 02 | Structured translation output + configurable model | None |
| 03 | Worker reliability + safe logging | 02 |
| 04 | Sentence-aware chunking + rolling context | 03 |
| 05 | Audio input device picker + line-input mode | None |
| 06 | Church Glossary | 04 |
| 07 | Transcript timeline + late-joiner backfill | 03 |
| 08 | Evaluation harness + golden set | 03, 04, 06 |
| 09 | Model/prompt A/B + default selection | 08 |
| 10 | Production deployment foundation | 01, 03, 07 |
| 11 | Operational hardening | 10 |
