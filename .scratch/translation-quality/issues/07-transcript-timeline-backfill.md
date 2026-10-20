# 07: Transcript timeline + late-joiner backfill

**What to build:** The current Live Feed keeps a shared Japanese Transcript Timeline and per-Language-Channel history. A listener joining an existing channel receives that channel's history. A listener joining a new or empty channel receives the recent Japanese transcript plus translations of the last 3 minutes (maximum 25 lines) in one batch call, shown as earlier history. A fresh Start clears history; Pause/Resume and reconnects keep it.

**Blocked by:** 03 — Worker reliability + safe logging.

**Status:** done

- [x] A shared Japanese Transcript Timeline exists for the current Live Feed.
- [x] Each Language Channel has its own translation history.
- [x] Joining an existing channel sends that channel's history.
- [x] Joining a new or empty channel sends Japanese history and a Backfill of the last 3 minutes / 25 lines in one batch call.
- [x] Concurrent joins to the same new channel do not trigger duplicate Backfills.
- [x] A fresh Start clears history; Pause/Resume and reconnects preserve it.
- [x] History begins at the first listener; zero listeners means no API calls.
- [x] Tests cover late join, new language, reconnect, fresh start, and zero-listener behavior.

## Comments

**2026-10-20** — Implemented and verified.

- **Implemented:** Added the in-memory shared Japanese Transcript Timeline, per-Language-Channel history, history delivery on join, and one batch Backfill of the last 3 minutes / 25 lines for a new or empty channel. Fresh Start clears history; Pause/Resume and reconnects preserve it. Concurrent joins share one Backfill through a room-level lock.
- **Verification:** `cd backend; ..\.venv\Scripts\python.exe -m pytest -q` -> `201 passed`; `python -m compileall -q app tests` -> passed. Manual verification pending real sermon audio.
- **Remaining:** Backfill failures are best-effort and leave that channel's history empty while the listener continues live; the next join retries. Per-room locking serializes backfills across languages. Real-audio/late-join timing not verified.
