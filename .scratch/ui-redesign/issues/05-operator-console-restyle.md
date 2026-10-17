# 05: Operator Console restyle

**What to build:** The console at the mixer wears the new identity with state colours doing the work: Feed Control buttons restyled with emerald Start/Resume kept as the feed action colour, the Live Feed State pill from the shared module (Stopped/Live/Paused) prominent and labelled, the QR Code panel on a white card with its heavier warm shadow so scanning and printing stay reliable, and the login card, room code, and actions (Download QR, Log out) restyled and obvious. Copy, auth, and control behaviour untouched.

Pointer: match the Operator Console — including its state gallery — in `docs/ui-redesign-visual.html`.

**Blocked by:** 01-theme-foundation, 02-shared-feed-state-visuals

**Status:** ready-for-agent

- [x] Console surfaces restyled with the sand/evergreen theme; no glass or blur
- [x] Feed Control buttons: emerald Start/Resume distinct from brand evergreen; Pause/Stop legible; behaviour unchanged
- [x] State pill/dot come from the shared module; labels unchanged
- [x] QR panel stays white with its heavier shadow; login card and room code restyled
- [x] All existing tests, lint, and `tsc -b` build pass

## Comments

- Implemented in `23a0720`. Feed Control now runs the state ramp (emerald live-btn Start/Resume, paused Pause, danger Stop — deliberately not the brand btn ramp); pill/dot come from `OPERATOR_STATE_VISUALS`; QR panel keeps plain `bg-white` under `shadow-qr`; login card, room-code chip, Download QR / Log out restyled. Copy, auth, and feed control behaviour untouched; 5 new tests.
- Verification at merge: 70 tests (65 + 5), lint/build clean.
- Review fix pass (`173a332`): operator inputs and buttons replaced the ~1.25:1 ring focus cue with the same visible `outline-focus` keyboard treatment as the guest view; feed-button ramps now come from `feedStateVisuals` (single owner).
