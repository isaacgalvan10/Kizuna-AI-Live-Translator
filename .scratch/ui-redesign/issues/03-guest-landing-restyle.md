# 03: Guest landing restyle (Language Picker)

**What to build:** The Language Picker a Guest reaches after scanning the QR Code wears the new identity end to end: pigmented sand surfaces with quiet borders (no glass, no blur), the 絆 brand mark set in the serif face, the three Guest Language buttons as the unmistakable primary action on the evergreen primary-button gradient, and the waiting/error states legible and calm. Copy, routes, and behaviour are untouched — this is a reskin plus within-structure polish, and the existing component tests must stay green.

Pointer: the settled look for this view is in the export at `docs/ui-redesign-visual.html` — match its Language Picker.

**Blocked by:** 01-theme-foundation

**Status:** ready-for-agent

- [x] Picker styled with the theme's sand surfaces and borders; no `backdrop-filter` remains
- [x] Brand mark in the serif face; language buttons on the primary-button treatment and clearly tappable
- [x] Pre-feed notice and error states restyled and legible against their surfaces; copy unchanged
- [x] Focus states visible; keyboard navigation unchanged
- [x] All existing tests, lint, and `tsc -b` build pass

## Comments

- Implemented in `134abed`: sand-card surface with 1px line border, serif 絆 KIZUNA mark over the gradient seam, three language buttons on the btn ramp with visible focus outlines, noticed/error states on the paused/danger families. Three new tests: retired-styles scan (no glass/palette drift), Tab+Enter activation, error-state rendering.
- Verification at merge: 56 tests (53 + 3), lint/build clean.
- Review fix pass (`173a332`) extracted the shared `BrandMark` component (previously duplicated in this view and the console, already drifted 32 vs 34px) and moved the focus outline onto the token-owned `outline-focus` treatment.
