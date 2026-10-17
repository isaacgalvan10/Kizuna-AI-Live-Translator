# 04: Listener View restyle

**What to build:** The Listener View reads like a text on the new identity. Translation and Japanese Transcript render as flowing sentences/short paragraphs with space between them — no per-line boxes — in Noto Serif JP at 18px or larger with a reading measure, while chrome (header, Spoken Translation toggle) goes quieter in sans. The Live Feed State pill and its dot come from the shared module (ticket 02), the interim line breathes via a `motion-safe` pulse, and the layout contract the tests pin — mobile stacking with translation first and the larger share, desktop two-pane grid, smart auto-follow — is untouched. All strings stay as they are.

Pointer: match the Listener View in `docs/ui-redesign-visual.html`.

**Blocked by:** 01-theme-foundation, 02-shared-feed-state-visuals

**Status:** ready-for-agent

- [x] Translation and Japanese Transcript use the flowing-text reading style (serif ≥18px, reading measure, spaced paragraphs, no per-line boxes)
- [x] State pill/dot come from the shared module; labels unchanged; live emerald with motion-safe pulse; colour never the only signal
- [x] Interim line distinct and breathing; suppressed under reduced motion
- [x] Chrome restyled (header, Audio toggle) with no behaviour change; smart scroll and history replay untouched
- [x] Layout-contract assertions in the existing suite stay green, plus all tests, lint, build

## Comments

- Implemented in `9d7dce2`. Translation reads at 19px/1.85 serif with a 34em measure, Japanese Transcript at 18px/1.8 with a 29em measure, both as borderless sentences/paragraphs — no per-line boxes; the interim line is the only boxed line and pulses under `motion-safe`. Pill/dot/labels come from `LISTENER_STATE_VISUALS`; header, Audio toggle (now `aria-pressed`), and banners restyled. Layout contract classes and all WebSocket/TTS/smart-scroll/history behaviour untouched; 5 new restyle tests.
- Verification at merge: 70 tests (65 + 5), lint/build clean.
- Deviation, kept deliberately: the Ended banner and pill wear the stopped grey family per the design doc, while the prototype paints Ended rose. Service ending is neutral, not an error; rose stays reserved for destructive/error. One-token change if the user prefers prototype parity.
