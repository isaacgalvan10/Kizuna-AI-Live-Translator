# 04: Guest QR landing page

**What to build:** New landing page at `/` (replaces current hub): QR code scans land here → language picker only (English, Korean, Chinese) → no room ID input, no Broadcaster button. POSTs to `/api/join/{qr_hash}`, then navigates to `/listen/{room_id}/{lang}`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Create new `GuestLanding` component in `frontend/src/components/GuestLanding.tsx`
- [ ] Replace `/` route in `App.tsx` with `GuestLanding`
- [ ] URL structure: `/?qr=<qr_code_hash>` (QR code contains this URL)
- [ ] On mount: extract `qr` from query string, call `POST /api/join/{qr_code_hash}`
- [ ] Response handling:
  - If `is_live=true` → navigate to `/listen/{room_id}/{lang}` with picked language
  - If `is_live=false` → show language picker, then navigate to `/listen/{room_id}/{lang}` with `is_live=false` (waiting state)
- [ ] Language picker: three options (en, ko, zh-hant) — no zh-hans per spec
- [ ] No room ID input, no Broadcaster button, no church/room selector
- [ ] Test: QR URL with valid hash → language picker → listener view; QR URL before operator starts → language picker → waiting state; invalid hash → error