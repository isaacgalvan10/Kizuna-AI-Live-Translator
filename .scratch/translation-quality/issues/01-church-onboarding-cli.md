# 01: Church onboarding CLI

**What to build:** A server-side command that onboards a church without the public dev seed endpoint. It creates or reuses the Church, its first Room, one operator login, and the church's permanent QR hash; it is safe to rerun; it rejects an email that belongs to another church; and it prints the join URL and operator URL. Passwords are read safely (interactive, stdin, or generated) and only hashes are stored.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] A new church run creates exactly one Church, one Room, one operator User, and a QR hash.
- [x] Re-running with the same arguments creates no duplicates and exits successfully.
- [x] A second operator email can be added to the same church without creating another church or room.
- [x] An email that belongs to another church or to a guest is rejected with a clear error and no partial writes.
- [x] `--reset-password` rotates the operator password; a normal rerun leaves it unchanged.
- [x] Passwords can be supplied interactively, via stdin, or generated; a generated password is printed once, and a supplied password is never printed.
- [x] Output includes the church and room IDs, operator email, QR hash, guest join URL (`/?qr=<hash>`), and operator URL (`/operate`).
- [x] Tests cover first run, rerun, second operator, cross-church rejection, and password reset.
- [x] The production onboarding path no longer depends on `/api/dev/seed`.

## Comments

- Implemented `backend/app/seed_church.py` and `backend/tests/test_seed_church.py`; README now documents the CLI.
- Verified with `pytest tests/test_seed_church.py -q` (17 passed: 10 data tests plus 7 CLI/password/output tests), the full backend suite (109 passed at final integration), and a manual CLI smoke test covering create, rerun, and password reset against SQLite.
- Review fix pass added CLI-level coverage for stdin and generated passwords, password mismatch, origin validation, printed join/operator URLs, database writes, and the missing-`DATABASE_URL` guard.
- All acceptance criteria are met; the production onboarding path no longer depends on `/api/dev/seed`, which remains local-only.
