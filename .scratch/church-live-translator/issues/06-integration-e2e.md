# 06: Integration & E2E

**What to build:** Wire all pieces together, test full operator→guest flow, verify tenancy isolation, test on real iOS/Android devices for TTS quality.

**Blocked by:** 01-database-migration-operator-auth, 02-feed-control-endpoints, 03-operator-console-ui, 04-guest-qr-landing, 05-listener-view-refactor

**Status:** ready-for-human

- [x] Verify full flow: operator logs into `/operate` → clicks Start → guest scans QR → picks language → lands on listener view → sees translations → enables Audio → hears TTS (backend: `tests/test_full_flow.py`; frontend: `src/App.test.tsx`)
- [x] Test Pause/Resume: operator clicks Pause → guest sees "Paused" banner, TTS stops → operator clicks Resume → guest sees live translations again
- [x] Test Stop: operator clicks Stop → guest sees "Service ended", Audio disabled
- [x] Test tenancy: create second church in DB; verify its operator cannot control first church's room; its QR only joins its room (also verifies no cross-room broadcast leakage over the live WebSocket)
- [x] Test pre-service scan: guest scans QR before operator starts → picks language → waits → operator starts → guest immediately sees translations (no re-scan)
- [ ] Real-device TTS test: open listener view on iOS Safari and Android Chrome; verify EN/KO/zh-CN voices are intelligible; document any language needing server TTS fallback — **manual step, cannot be done from CI/agent; run before Sunday**
- [x] Clean up: remove deprecated `/preacher` route and `PreacherDashboard` component (route was removed in ticket 03; orphaned component deleted here)
- [x] Update `/api/dev/seed` to create test operator user with `is_guest=false` and `church_id` (done in ticket 01, covered by `test_dev_seed_creates_operator_that_can_log_in`)
- [x] Test: all acceptance criteria from spec.md pass (except the documented US8 edge case: a guest who refreshes while paused lands on "Waiting" — see the known limitation below)

## Comments

- Ticket 06 verification: 54 backend tests passing (`backend/tests/test_full_flow.py` drives the real HTTP + WebSocket endpoints through TestClient with a fake Gemini worker standing in for the external AI call), 46 frontend tests passing (new `frontend/src/App.test.tsx` walks scan → language picker → listener → live → audio ON → pause → resume → stop through the real router with mocked transport), lint and `tsc -b` build clean.
- Known limitation from ticket 05: a guest who refreshes while the feed is paused lands on "Waiting" instead of "Paused". `Room.is_live` stays true through a pause (needed so the QR join still resolves to the room), so the boolean cannot distinguish paused from waiting on connect. Options if it matters in practice: persist a tri-state feed state on `Room`, or send the last broadcast state to a room on WebSocket connect.
- Real-device TTS checklist for the operator before Sunday (manual): on iOS Safari and Android Chrome, (1) open the listener view, tap Audio ON, confirm the primer does not throw and a translation speaks; (2) confirm EN, KO, and zh-CN voices are intelligible and language-matched; (3) Pause cancels speech mid-line; (4) Audio OFF stops speech; (5) note any language whose voice is missing/robotic enough to warrant the server-TTS fallback.