# 01: Database migration & operator auth

**What to build:** Add `church_id` column to User model for tenancy. Create `POST /api/operator/login` endpoint that validates email/password, scopes to a church, and returns a JWT with `church_id` claim. Protect operator endpoints with this auth.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Add `church_id` (Integer, ForeignKey to `churches.id`, nullable=True) to `User` model in `backend/app/models.py`
- [ ] Create Alembic migration (or SQLAlchemy `create_all` handles it on startup) for the new column
- [ ] Implement `POST /api/operator/login` in `backend/app/main.py`:
  - Accept email/password
  - Verify against `User` where `is_guest=false` and `church_id` matches
  - Return JWT with `church_id` claim
- [ ] Create auth dependency `get_current_operator` that validates JWT and returns `church_id`
- [ ] Seed a test operator user for the test church (via `/api/dev/seed` or new endpoint)
- [ ] Test: valid login returns token with correct `church_id`; invalid credentials rejected; guest users cannot log in