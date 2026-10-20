# Implementation Summaries

How to report a completed ticket. This extends the global End-of-Task Summary: the five standard headings keep their meaning, and this file adds the depth a ticket needs.

## When

Finish the ticket in this order:

1. Meet the acceptance criteria and run verification.
2. Append the compact ticket record (below) to `## Comments` and set `Status: done`.
3. Commit the work.
4. Present the six-section summary in chat.

- **One ticket:** summarize that ticket.
- **`/implement-spec`:** summarize once at integration, not once per implementer subagent.
- **Partial work:** leave `Status` unchanged and use **Remaining** to state what is unfinished.

## Shape

Keep the five standard headings in their usual order, then add **Tutor**:

1. **Implemented** — what changed in observable behavior, in 2–3 bullets. Separate the user-visible change from internal plumbing.
2. **Why** — the one or two decisions that mattered, each with the constraint behind it. Name a rejected alternative when the choice was not obvious.
3. **Verification** — automated checks actually run, then manual steps (below).
4. **Learned** — your own takeaway from doing the work: what was tricky, surprising, or worth doing differently next time. One or two sentences.
5. **Remaining** — risks, assumptions, follow-ups, and unresolved questions.
6. **Tutor** — the teaching section (below).

Target roughly 250–350 words across the six sections, excluding commands and code. One idea per bullet; define jargon on first use.

## Verification

Report two kinds of evidence, clearly separated.

**Automated** — the exact command and its result, e.g. `cd backend && pytest -q` → `180 passed`. List a check as passed only when it actually ran.

**Manual** — numbered, copy-paste steps the user can follow: a command, a URL, or a click path; the expected result; and a one-line failure symptom. Every ticket that changes runtime behavior gets manual steps.

For a pure refactor or internal change, write `No manual check — covered by <tests>` and say why.

Finish with anything not verified, so the gap is explicit.

## Tutor

This is where the user learns. Teach one or two ideas, simply:

- Name the concept, architecture pattern, or design principle the ticket exercised.
- Explain what it is and why it exists in one or two short paragraphs, using the user's frontend knowledge as the bridge.
- Connect it to this codebase: name the file and the mechanism.
- Optionally close with one interview-style sentence: "If asked about X, say Y."

Teach inline as decisions happen (global section 4); Tutor recaps the single most important concept. Prefer one idea explained well over three mentioned.

## Ticket record

Show the full six-section summary in chat. The ticket's `## Comments` entry stays compact — only **Implemented**, **Verification**, and **Remaining** — so the tracker keeps a durable record without duplicating the teaching.

```md
**YYYY-MM-DD** — Implemented and verified.

- **Implemented:** ...
- **Verification:** ...
- **Remaining:** ...
```

## Example

```md
## Verification

**Automated:** `cd backend && pytest -q` → `180 passed`; `cd frontend && npm test` → `45 passed`.

**Manual:**
1. `docker compose up --build`, then `curl -X POST http://localhost:8000/api/dev/seed`.
2. Open `http://localhost:5173/operate` and log in as `operator@kizuna.test` / `kizuna-operator-test`.
3. Press **Start**, speak into the mixer input, and open a guest view.
   Expected: translation lines arrive within a few seconds.
   Failure looks like: no line after 10 seconds, or the badge stays **Stopped**.
4. Press **Pause**. Expected: the guest sees the Paused banner and TTS stops.
   Failure looks like: new lines keep arriving while paused.

**Not verified:** real-device TTS quality (manual, before Sunday).
```
