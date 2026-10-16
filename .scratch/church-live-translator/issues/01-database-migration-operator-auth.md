# 01: Database migration & operator auth

**What to build:** Add `church_id` column to User model for tenancy. Create `POST /api/operator/login` endpoint that validates email/password, scopes to a church, and returns a JWT with `church_id` claim. Protect operator endpoints with this auth.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] Add `church_id` (Integer, ForeignKey to `churches.id`, nullable=True) to `User` model in `backend/app/models.py`
- [x] Create Alembic migration (or SQLAlchemy `create_all` handles it on startup) for the new column
- [x] Implement `POST /api/operator/login` in `backend/app/main.py`:
  - Accept email/password
  - Verify against `User` where `is_guest=false` and `church_id` matches
  - Return JWT with `church_id` claim
- [x] Create auth dependency `get_current_operator` that validates JWT and returns `church_id`
- [x] Seed a test operator user for the test church (via `/api/dev/seed` or new endpoint)
- [x] Test: valid login returns token with correct `church_id`; invalid credentials rejected; guest users cannot log in

## Comments

Implemented with bcrypt (password hashing) and python-jose (HS256 JWT) instead of the declared `passlib`, which is unmaintained and crashes with modern `bcrypt` on Python 3.14. Auth logic lives in `backend/app/auth.py` (`get_operator_claims`, `get_current_operator`); `GET /api/operator/me` is the first protected consumer. `/api/dev/seed` is now idempotent and seeds operator `operator@kizuna.test` / `kizuna-operator-test` for the test church.

Tests: `backend/tests/test_operator_auth.py` (12 passing) run against in-memory SQLite via a `get_db` dependency override; run with `python -m pytest` from `backend/` after `pip install -r requirements-dev.txt`.

Caveat: no Alembic migration — startup `create_all` creates missing tables but does not add `church_id` to a pre-existing `users` table, so an old dev Postgres volume must be dropped and re-seeded via `/api/dev/seed`.

Deferred: `/ws/stream/{room_id}` is still unauthenticated (spec mentions protecting it). Adding a token requirement now would break the existing `/preacher` page before `/operate` exists in ticket 03; pick it up there. Set `JWT_SECRET_KEY` in `.env` (done locally) — tokens are forgeable with the code fallback secret.