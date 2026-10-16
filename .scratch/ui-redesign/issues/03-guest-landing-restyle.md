# 03: Guest landing restyle (Language Picker)

**What to build:** The Language Picker a Guest reaches after scanning the QR Code wears the new identity end to end: pigmented sand surfaces with quiet borders (no glass, no blur), the 絆 brand mark set in the serif face, the three Guest Language buttons as the unmistakable primary action on the evergreen primary-button gradient, and the waiting/error states legible and calm. Copy, routes, and behaviour are untouched — this is a reskin plus within-structure polish, and the existing component tests must stay green.

Pointer: the settled look for this view is in the export at `docs/ui-redesign-visual.html` — match its Language Picker.

**Blocked by:** 01-theme-foundation

**Status:** ready-for-agent

- [ ] Picker styled with the theme's sand surfaces and borders; no `backdrop-filter` remains
- [ ] Brand mark in the serif face; language buttons on the primary-button treatment and clearly tappable
- [ ] Pre-feed notice and error states restyled and legible against their surfaces; copy unchanged
- [ ] Focus states visible; keyboard navigation unchanged
- [ ] All existing tests, lint, and `tsc -b` build pass
