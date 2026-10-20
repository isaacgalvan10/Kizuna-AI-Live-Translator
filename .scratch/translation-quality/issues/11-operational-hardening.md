# 11: Operational hardening

**What to build:** The deployment can be operated safely week to week: database backups are restorable, the service is monitored, logs do not fill the disk, and costs are visible.

**Blocked by:** 10 — Production deployment foundation.

**Status:** ready-for-agent

- [ ] A nightly Postgres backup runs and a restore has been verified.
- [ ] The health endpoint is monitored externally with an alert.
- [ ] Log rotation is configured, and sermon text is not retained by default.
- [ ] A simple monthly cost view or report is available from token usage records.
- [ ] A runbook covers start/stop, onboarding a church, rotating an operator password, and restoring a backup.
- [ ] Secrets live outside the repository and can be rotated.
- [ ] The service restarts automatically after a reboot or crash.
