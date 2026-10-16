# 03: Operator console UI

**What to build:** New `/operate` route in frontend: login form → Start/Pause/Stop buttons with status indicator. Bookmarkable URL. No guest access. Replaces deprecated `/preacher` route.

**Blocked by:** 01-database-migration-operator-auth, 02-feed-control-endpoints

**Status:** ready-for-agent

- [x] Create new `OperatorConsole` component in `frontend/src/components/OperatorConsole.tsx`
- [x] Add `/operate` route in `App.tsx` (replace `/preacher` route)
- [x] Login form: email/password inputs, submit calls `POST /api/operator/login`, stores JWT in localStorage
- [x] After login: show church name, room ID, Start/Pause/Stop buttons, status badge (Live/Paused/Stopped)
- [x] Buttons call respective feed control endpoints (ticket 02)
- [x] Status indicator reflects `feed_state` from WebSocket (subscribe to room's feed_state events)
- [x] Logout button clears JWT, returns to login form
- [x] Style: clean, high-contrast for sound booth visibility; large touch targets for wet hands
- [x] Test: login works; buttons call APIs; status updates on feed_state; logout works; inaccessible without login

## Comments

Scope additions beyond the checklist, all required to make the checklist work:

- **`GET /api/operator/church`** (auth, new): returns `{ id, name, rooms: [{ id, is_live }] }` for the token's church. Nothing exposed church name or room IDs, and the console must show both. The console picks `rooms[0]`; a room picker is deferred until a church actually has more than one room (MVP seed creates one room).
- **`/ws/stream/{room_id}` now requires the operator JWT** (picks up the deferral from ticket 01). Browsers cannot set headers on a WebSocket handshake, so the token rides as `?token=`. Room is looked up tenancy-scoped; failures are rejected before accept — starlette's TestClient surfaces that as close code 1008, but uvicorn (the real server) answers a pre-accept close with an HTTP 403 instead of upgrading, so a browser only ever sees a generic 1006 drop. `room_id` is now an int (was free-form string) so it lines up with the feed control endpoints and `Room.id`.
- **Operator channel**: the console subscribes to `/ws/listen/{room_id}/operator` for `feed_state` events. `get_active_languages` now excludes this `operator` bucket, otherwise the Gemini worker would treat the console as a listener and burn API calls translating to nobody.

Frontend notes:

- `App.tsx`'s inline preacher streaming code is deleted; the landing "Dashboard" button points at `/operate` until ticket 04 replaces the landing page. `PreacherDashboard.tsx` file remains for ticket 06 to clean up.
- Pause gates the audio processor (`isSendingAudio` ref) instead of tearing down capture, so Resume is instant; the backend stays deliberately forgiving and the console hides invalid actions (Pause disabled unless live, Stop disabled unless live/paused, Start/Resume disabled while live).
- The audio pipeline opens before the `start` POST, so a mic-permission failure leaves the feed stopped with an error instead of a live feed with no audio.
- Initial badge comes from `is_live`, the only feed state the database persists: pause does not clear `is_live`, so a console that loads mid-pause is initially labelled "Live" until the next `feed_state` event. Slightly misleading, but the console cannot know better until feed state is persisted/replayed — same gap ticket 02 deferred to ticket 05.
- `api.js` → `api.ts` (renamed): TypeScript cannot import the untyped `.js` under the current tsconfig.
- Frontend had no test infrastructure; added vitest 5 + jsdom + Testing Library (19 tests, `npm run test` from `frontend/`). A `FakeWebSocket` + stubbed `AudioContext`/`getUserMedia` let the component tests drive login, control endpoints, badge updates, stream-failure copy, and logout through the DOM.
- Failure copy distinguishes causes a wrong message would mislead on: login reports an unreachable server separately from bad credentials, and a stream socket that never opened ("check the connection") is separated from one dropped mid-broadcast ("press Stop, then Start") — after a mid-broadcast drop the operator is still "Live" server-side, so Start is disabled and Stop-then-Start is the only working path.

Backend tests: `test_operator_church.py`, `test_stream_auth.py` (real handshake via starlette TestClient against a temp-file SQLite DB), `test_socket_manager.py`. Full backend suite 41 passing (`..\.venv\Scripts\python.exe -m pytest` from `backend/`).

Env note: the local `.env` is missing a newline between `DATABASE_URL` and `JWT_SECRET_KEY`, so `DATABASE_URL` swallows the JWT key value; local (non-test) backend runs need that fixed. Untouched because it is gitignored and holds secrets.
