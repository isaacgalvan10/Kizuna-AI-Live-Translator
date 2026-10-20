# 10: Production deployment foundation

**What to build:** A small Tokyo VPS runs the app and Postgres behind HTTPS at a stable domain. The operator logs in and captures audio; a phone on cellular scans the QR code and listens. The church installs nothing.

**Blocked by:** 01 — Church onboarding CLI; 03 — Worker reliability + safe logging; 07 — Transcript timeline + late-joiner backfill.

**Status:** ready-for-agent

- [ ] The VPS runs the backend, Postgres, and a reverse proxy with automatic HTTPS through Docker Compose.
- [ ] Production environment sets the database URL, Gemini key, JWT secret, and public origin; no development defaults remain.
- [ ] CORS and WebSocket origins allow only the production domain.
- [ ] The onboarding CLI creates a real church, operator, room, and QR hash on the VPS.
- [ ] Operator login works at `/operate`; the QR points to the stable domain.
- [ ] A phone on cellular can scan the QR, pick a language, and receive live text.
- [ ] The service survives a container restart and listeners can reconnect.
- [ ] A Google billing budget alert is configured at the agreed threshold.
- [ ] `/api/dev/seed` is disabled or removed in production.
