# 04: Listener View restyle

**What to build:** The Listener View reads like a text on the new identity. Translation and Japanese Transcript render as flowing sentences/short paragraphs with space between them — no per-line boxes — in Noto Serif JP at 18px or larger with a reading measure, while chrome (header, Spoken Translation toggle) goes quieter in sans. The Live Feed State pill and its dot come from the shared module (ticket 02), the interim line breathes via a `motion-safe` pulse, and the layout contract the tests pin — mobile stacking with translation first and the larger share, desktop two-pane grid, smart auto-follow — is untouched. All strings stay as they are.

Pointer: match the Listener View in `docs/ui-redesign-visual.html`.

**Blocked by:** 01-theme-foundation, 02-shared-feed-state-visuals

**Status:** ready-for-agent

- [ ] Translation and Japanese Transcript use the flowing-text reading style (serif ≥18px, reading measure, spaced paragraphs, no per-line boxes)
- [ ] State pill/dot come from the shared module; labels unchanged; live emerald with motion-safe pulse; colour never the only signal
- [ ] Interim line distinct and breathing; suppressed under reduced motion
- [ ] Chrome restyled (header, Audio toggle) with no behaviour change; smart scroll and history replay untouched
- [ ] Layout-contract assertions in the existing suite stay green, plus all tests, lint, build
