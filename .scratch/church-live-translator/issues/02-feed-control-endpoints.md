# 02: Feed control endpoints

**What to build:** Implement operator feed control endpoints (`POST /api/operator/rooms/{room_id}/start`, `/pause`, `/stop`) that update `Room.is_live` and broadcast `feed_state` events to all listeners via WebSocket. Requires operator auth from ticket 01.

**Blocked by:** 01-database-migration-operator-auth

**Status:** ready-for-agent

- [ ] Add `feed_state` enum/constant: `"live" | "paused" | "stopped"`
- [ ] Implement `POST /api/operator/rooms/{room_id}/start` (auth required via ticket 01):
  - Verify room belongs to operator's `church_id`
  - Set `Room.is_live = True`
  - Broadcast `{ type: "feed_state", data: "live" }` to all listeners in room via WebSocket manager
- [ ] Implement `POST /api/operator/rooms/{room_id}/pause`:
  - Verify ownership
  - Broadcast `{ type: "feed_state", data: "paused" }` (keep `is_live=true` so room stays findable)
- [ ] Implement `POST /api/operator/rooms/{room_id}/stop`:
  - Verify ownership
  - Set `Room.is_live = False`
  - Broadcast `{ type: "feed_state", data: "stopped" }`
- [ ] Extend WebSocket manager (`socket_manager.py`) to support broadcasting `feed_state` to all language channels in a room
- [ ] Test: operator can start/pause/stop; listeners receive feed_state events; other churches' operators cannot control this room