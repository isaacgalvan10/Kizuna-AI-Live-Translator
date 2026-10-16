# 06: Integration & E2E

**What to build:** Wire all pieces together, test full operator→guest flow, verify tenancy isolation, test on real iOS/Android devices for TTS quality.

**Blocked by:** 01-database-migration-operator-auth, 02-feed-control-endpoints, 03-operator-console-ui, 04-guest-qr-landing, 05-listener-view-refactor

**Status:** ready-for-agent

- [ ] Verify full flow: operator logs into `/operate` → clicks Start → guest scans QR → picks language → lands on listener view → sees translations → enables Audio → hears TTS
- [ ] Test Pause/Resume: operator clicks Pause → guest sees "Paused" banner, TTS stops → operator clicks Resume → guest sees live translations again
- [ ] Test Stop: operator clicks Stop → guest sees "Service ended", Audio disabled
- [ ] Test tenancy: create second church in DB; verify its operator cannot control first church's room; its QR only joins its room
- [ ] Test pre-service scan: guest scans QR before operator starts → picks language → waits → operator starts → guest immediately sees translations (no re-scan)
- [ ] Real-device TTS test: open listener view on iOS Safari and Android Chrome; verify EN/KO/zh-CN voices are intelligible; document any language needing server TTS fallback
- [ ] Clean up: remove deprecated `/preacher` route and `PreacherDashboard` component
- [ ] Update `/api/dev/seed` to create test operator user with `is_guest=false` and `church_id`
- [ ] Test: all acceptance criteria from spec.md pass