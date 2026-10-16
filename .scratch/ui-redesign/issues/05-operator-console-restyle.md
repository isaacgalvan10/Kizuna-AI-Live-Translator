# 05: Operator Console restyle

**What to build:** The console at the mixer wears the new identity with state colours doing the work: Feed Control buttons restyled with emerald Start/Resume kept as the feed action colour, the Live Feed State pill from the shared module (Stopped/Live/Paused) prominent and labelled, the QR Code panel on a white card with its heavier warm shadow so scanning and printing stay reliable, and the login card, room code, and actions (Download QR, Log out) restyled and obvious. Copy, auth, and control behaviour untouched.

Pointer: match the Operator Console — including its state gallery — in `docs/ui-redesign-visual.html`.

**Blocked by:** 01-theme-foundation, 02-shared-feed-state-visuals

**Status:** ready-for-agent

- [ ] Console surfaces restyled with the sand/evergreen theme; no glass or blur
- [ ] Feed Control buttons: emerald Start/Resume distinct from brand evergreen; Pause/Stop legible; behaviour unchanged
- [ ] State pill/dot come from the shared module; labels unchanged
- [ ] QR panel stays white with its heavier shadow; login card and room code restyled
- [ ] All existing tests, lint, and `tsc -b` build pass
