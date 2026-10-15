# 03: Operator console UI

**What to build:** New `/operate` route in frontend: login form → Start/Pause/Stop buttons with status indicator. Bookmarkable URL. No guest access. Replaces deprecated `/preacher` route.

**Blocked by:** 01-database-migration-operator-auth, 02-feed-control-endpoints

**Status:** ready-for-agent

- [ ] Create new `OperatorConsole` component in `frontend/src/components/OperatorConsole.tsx`
- [ ] Add `/operate` route in `App.tsx` (replace `/preacher` route)
- [ ] Login form: email/password inputs, submit calls `POST /api/operator/login`, stores JWT in localStorage
- [ ] After login: show church name, room ID, Start/Pause/Stop buttons, status badge (Live/Paused/Stopped)
- [ ] Buttons call respective feed control endpoints (ticket 02)
- [ ] Status indicator reflects `feed_state` from WebSocket (subscribe to room's feed_state events)
- [ ] Logout button clears JWT, returns to login form
- [ ] Style: clean, high-contrast for sound booth visibility; large touch targets for wet hands
- [ ] Test: login works; buttons call APIs; status updates on feed_state; logout works; inaccessible without login