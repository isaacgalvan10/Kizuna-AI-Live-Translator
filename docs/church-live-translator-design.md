# Church Live Translator Design

## Summary

A real-time translation system for Japanese Christian church services in Osaka. The operator starts a live feed from a mixer-connected laptop; guests scan a QR code, pick English, Korean, Chinese, and listen on headphones while reading Japanese transcript and translation stacked on their phone. The operator pauses the feed during worship music. Each church owns its live feed and operator accounts; a second church gets its own isolated tenancy. Browser TTS keeps recurring cost at zero, with server TTS as a fallback only if a language proves unusable on real devices.

## Terms

| Term | Definition | Avoid |
|------|------------|-------|
| operator | The person who starts, pauses, and stops the live feed; not necessarily the preacher. | preacher, admin, host |
| live feed | The operator-controlled stream of transcribed Japanese plus translations that listeners join. | broadcast, room stream |
| guest | An attendee who joins via QR, picks a language, and listens on their phone. | user, client |
| operator login | An authenticated person allowed to start, pause, and stop one church's live feed. | admin, superuser |
| church tenancy | Every live feed, QR, and operator belongs to exactly one church; another church cannot see or control it. | multi-tenant org, workspace |

## Why

Design a real-time translator for a Japanese Christian church service in Osaka: transcribe Japanese (with occasional English words and a second speaker), show translations side by side, let attendees listen on headphones, pause during worship music, and join by scanning a QR code after an operator starts the live feed.

## Locked Decisions (Durable)

### Q1: How does a guest enter from the pew?
**Decision: A** — QR opens a language picker only, then connects to this church's current live feed (no room ID, no operator controls).
**Rejected:**
- B (keep hub with room ID): leaks operator UI onto phones in the pew and adds a room ID guests should never need.
- C (QR lands on hub with pre-filled room ID): same leak, plus still exposes the Broadcaster button.

### Q2: Where does the Japanese audio come from?
**Decision: B** — Aux/line feed from the church mixer (same mics as the PA).
**Rejected:**
- A (operator laptop/phone mic): hears singing, clapping, congregation — wrecks transcription and music-pause.
- C (dedicated recorder on pulpit): misses handheld mics off the pulpit.

### Q3: Who pauses the live feed during worship music?
**Decision: A** — Operator Pause/Resume only; guests see Paused and TTS stops.
**Rejected:**
- B (automatic music detection): false pauses during speech over pads lose sermon sentences; bets the service on unreliable detection.
- C (detector suggests, operator confirms): adds a prompt the operator will ignore under load.

### Q4: How does the operator reach Start/Pause/Stop?
**Decision: A** — A separate operator URL (bookmark on the mixer laptop); no PIN.
**Rejected:**
- B (PIN): mistyped with wet hands between songs; written on console; session expiry mid-sermon locks out operator.
- C (second QR on sound booth): Q1 forbade operator controls on guest QR; phone-as-operator fights Q2 (mixer aux is on laptop).

### Q6: What if someone scans before the operator starts?
**Decision: C** — Let them pick a language, then wait on the listener view until the feed goes live.
**Rejected:**
- A (waiting room only): delays the only guest decision (language) until sermon is moving.
- B (error, scan again): trains people to think the QR is broken.

### Q7: Who is allowed to log in as this church's operator?
**Decision: A** — One shared church login (email + password) on the mixer laptop.
**Rejected:**
- B (per-volunteer accounts): requires invite/revoke UI before Sunday; volunteer must remember password; mixer laptop may need multiple browser profiles.
- C (magic link): mixer laptop often has no email client or internet; requires SMTP infra; link expiry mid-service locks out operator with no fallback.

### Q9: What speaks into the guest's headphones?
**Decision: A** — Keep on-device browser TTS, one utterance per translation line.
**Rejected:**
- B (server TTS): recurring cost, new infra; not needed unless a language is unusable.
- C (browser now, swap later): user explicitly wants zero recurring cost; browser TTS is the baseline, server TTS only if testing proves a language unusable.

## Routine Choices (Non-Durable)

### Q5: Which languages sit on the QR picker?
**Decision: A** — English, Korean, 中文 (Chinese) only.
Originally shipped as 繁體中文 (Traditional); the user switched it to a single plain Chinese option in Simplified (`zh-hans`, zh-CN voice) after testing the picker — Simplified is the native script for the largest audience, and Traditional readers generally follow it. Traditional stays a one-line picker change: the Gemini prompt and both language codes already exist.

### Q8: How does Japanese sit next to the translation on a phone?
**Decision: B** — Stacked: translation on top, Japanese scrolling underneath, both always visible.
Desktop stays true two-pane. Stacked preserves side-by-side intent on 6-inch screens without 8pt type.

## Verified Facts

- Backend already has `POST /api/join/{qr_code_hash}` that finds the church and any `is_live` room.
- User table exists with `email`, `hashed_password`, `is_guest`; needs `church_id` column for tenancy.
- Current `/preacher` route in `App.tsx` already has Start/Pause/Stop buttons; Q4 mostly hides it from the guest hub.
- Listener view already shows transcript + translation side by side on desktop; hides Japanese below `sm` breakpoint.
- Browser `speechSynthesis` works for EN/KO/zh-TW today; voices differ by device (iOS vs Android).
- Pause (Q3) cancels speech regardless of TTS source.

## Risks

1. **Shared operator login (Q7-A)** leaks when a volunteer leaves; no per-person revocation. Mitigation: rotate password after any departure; treat as operational habit for Osaka this Sunday.
2. **Operator URL on bookmark (Q4-A)** is a single factor; anyone with LAN access or leaked bookmark can start/stop. Mitigation: keep URL off paper at booth; send via LINE/email to substitute operators.
3. **Browser TTS quality (Q9-A)** varies by device; Korean and 繁體 may be unintelligible on some phones. Mitigation: test on real iOS/Android devices before Sunday; server TTS is the documented fallback.
4. **Mixer aux dependency (Q2-B)** requires physical cable and operator laptop always plugged in. Mitigation: spare cable in booth; document setup checklist for volunteer.
5. **Auto-pause deferred (Q3-A)** — if operator misses a worship transition, song lyrics are spoken over. Mitigation: operator rehearsal; visual "Paused" banner on listener view is clear.

## Deferred

- Automatic music detection for pause/resume (Q3-B/C) — revisit after Osaka Sunday if operator burden is high.
- Per-volunteer operator accounts (Q7-B) — build invite/revoke UI if shared login proves painful.
- Server TTS (Q9-B) — only if browser voices fail real-device testing.
- Simplified Chinese (Q5-B) — add when TTS and prompts are ready.

## Open Threads

- Q4 thread: user asked how to secure tenancy across churches; answered by binding User to Church via `church_id` and scoping live feed to that `church_id`. No further discussion.
- Q9 thread: user emphasized zero recurring cost; acknowledged with server TTS as conditional fallback only.