# 02: Feed control endpoints

**What to build:** Implement operator feed control endpoints (`POST /api/operator/rooms/{room_id}/start`, `/pause`, `/stop`) that update `Room.is_live` and broadcast `feed_state` events to all listeners via WebSocket. Requires operator auth from ticket 01.

**Blocked by:** 01-database-migration-operator-auth

**Status:** ready-for-agent

- [x] Add `feed_state` enum/constant: `"live" | "paused" | "stopped"`
- [x] Implement `POST /api/operator/rooms/{room_id}/start` (auth required via ticket 01):
  - Verify room belongs to operator's `church_id`
  - Set `Room.is_live = True`
  - Broadcast `{ type: "feed_state", data: "live" }` to all listeners in room via WebSocket manager
- [x] Implement `POST /api/operator/rooms/{room_id}/pause`:
  - Verify ownership
  - Broadcast `{ type: "feed_state", data: "paused" }` (keep `is_live=true` so room stays findable)
- [x] Implement `POST /api/operator/rooms/{room_id}/stop`:
  - Verify ownership
  - Set `Room.is_live = False`
  - Broadcast `{ type: "feed_state", data: "stopped" }`
- [x] Extend WebSocket manager (`socket_manager.py`) to support broadcasting `feed_state` to all language channels in a room
- [x] Test: operator can start/pause/stop; listeners receive feed_state events; other churches' operators cannot control this room

## Comments

Decisions confirmed with maintainer: backend is deliberately forgiving (any action accepted at any time; the operator UI is the gatekeeper that hides invalid actions), and cross-church room access returns 404 so room IDs don't leak across tenants.

Implementation: `FeedState` Literal + `FEED_STATE_*` constants in `socket_manager.py`; `ConnectionManager.broadcast_feed_state(room_id, state)` fans out to every language channel and reuses the existing dead-connection cleanup pattern. `main.py` has a shared `_apply_feed_control` helper (tenancy-scoped `select`, optional `is_live` update, broadcast) backing the three endpoints; `pause` leaves `is_live` untouched. Response contract: `{ status: "live" | "paused" | "stopped" }` (`FeedControlResponse` in `schemas.py`).

Tests: `backend/tests/test_feed_control.py` (17 tests) covers 401 without token, tenancy 404s for all three actions, `is_live` transitions, idempotent start, resume-after-pause, and WS fan-out using fake socket objects registered on the real `ConnectionManager`. Run with `..\.venv\Scripts\python.exe -m pytest` from `backend/`; full suite 30 passing.

Env note: the repo-root `.venv` was missing PyJWT (`auth.py` imports `jwt`, but the venv had `python-jose`); installed `pyjwt==2.15.1` to match `requirements.txt`. The declared `python-jose` dependency appears unused.

Deferred: listeners who connect *after* a pause/stop get no `feed_state` on connect — they only see `is_live` via `POST /api/join/...`. Ticket 05 (listener view) should decide whether `connect()` should replay the current feed state (requires DB access in the WS handler, or state cached on the manager).