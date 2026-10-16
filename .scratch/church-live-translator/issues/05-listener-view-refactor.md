# 05: Listener view refactor

**What to build:** Refactor existing `/listener` route to `/listen/{room_id}/{lang}` with: stacked layout on mobile (translation top, Japanese bottom), "Waiting for operator" state when `is_live=false`, "Paused" banner on `feed_state=paused`, Audio ON/OFF toggle with browser TTS, TTS cancellation on Pause/language change/Audio OFF.

**Blocked by:** 02-feed-control-endpoints, 04-guest-qr-landing

**Status:** ready-for-agent

- [x] Rename `/listener` route to `/listen/:roomId/:lang` in `App.tsx`
- [x] Update `Listener` component to accept `roomId` and `lang` from route params
- [x] Layout changes:
  - Mobile (<md): stacked — translation column full width (order-1), Japanese column below (order-2), both always visible
  - Desktop (md+): keep existing two-pane side-by-side
- [x] Waiting state: when `is_live=false` (from QR join response), show "Waiting for operator to start the feed…" centered in translation panel; disable Audio toggle
- [x] Paused state: listen for `feed_state` WebSocket events; on `"paused"` show "Paused — worship music" banner, cancel TTS; on `"live"` hide banner; on `"stopped"` show "Service ended" and disable Audio
- [x] TTS handling:
  - Audio ON: primer utterance "Audio active" (existing), then speak each translation line
  - Audio OFF: `speechSynthesis.cancel()`
  - Language change: cancel current, prime new voice
  - Pause event: cancel TTS immediately
- [x] Test: stacked layout on mobile; waiting state shows before operator starts; paused banner appears on Pause; TTS toggles and cancels correctly; desktop two-pane unchanged

## Comments

- Landing contract from ticket 04: `GuestLanding` navigates to `/listen/{room_id}/{lang}` with router state `{ isLive: boolean }` taken from the join response. Router state survives only the in-app navigation (lost on refresh or a directly opened URL), so the listener view should treat `feed_state` WebSocket events as the source of truth after mount and keep its Waiting state until an event says otherwise.
- Decisions confirmed with the user before building:
  - Mobile keeps two independent scroll panes (translation flex-[3], Japanese flex-[2]) with a near-bottom smart-scroll: auto-follow the newest line unless the guest has scrolled back.
  - Joining late / refreshing shows history: the backend already replays its per-language history buffer on connect, and the listener renders those `history` messages. A refresh mid-pause still shows Waiting because `Room.is_live` stays true during pause (no persisted paused state), so the boolean cannot distinguish waiting from paused on connect.
  - Interim (`interim_translation`) lines are shown in dashed italic blocks and are never spoken; the first translation (or interim) arriving while Waiting is treated as proof the feed is live.
- A `feed_state` event carrying `"paused"`/`"stopped"` cancels TTS; `"stopped"` also switches Audio OFF and disables the toggle, and `"live"` re-enables it.
