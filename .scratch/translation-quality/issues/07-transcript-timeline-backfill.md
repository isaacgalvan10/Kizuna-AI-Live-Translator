# 07: Transcript timeline + late-joiner backfill

**What to build:** The current Live Feed keeps a shared Japanese Transcript Timeline and per-Language-Channel history. A listener joining an existing channel receives that channel's history. A listener joining a new or empty channel receives the recent Japanese transcript plus translations of the last 3 minutes (maximum 25 lines) in one batch call, shown as earlier history. A fresh Start clears history; Pause/Resume and reconnects keep it.

**Blocked by:** 03 — Worker reliability + safe logging.

**Status:** ready-for-agent

- [ ] A shared Japanese Transcript Timeline exists for the current Live Feed.
- [ ] Each Language Channel has its own translation history.
- [ ] Joining an existing channel sends that channel's history.
- [ ] Joining a new or empty channel sends Japanese history and a Backfill of the last 3 minutes / 25 lines in one batch call.
- [ ] Concurrent joins to the same new channel do not trigger duplicate Backfills.
- [ ] A fresh Start clears history; Pause/Resume and reconnects preserve it.
- [ ] History begins at the first listener; zero listeners means no API calls.
- [ ] Tests cover late join, new language, reconnect, fresh start, and zero-listener behavior.
