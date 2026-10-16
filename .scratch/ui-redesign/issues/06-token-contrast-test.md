# 06: Token contrast test

**What to build:** The spec's AA promise becomes a CI check. A Vitest suite reads the `@theme` token block from the global stylesheet (single source of truth — no duplicated hex values), computes WCAG contrast ratios, and fails when a palette tweak breaks accessibility: body/reading text pairs at 4.5:1 or better, large-text/UI pairs at 3:1 or better, with translucent state backgrounds composited over the sand base before measuring. It runs against the final tokens, after every view has landed.

**Blocked by:** 01-theme-foundation, 03-guest-landing-restyle, 04-listener-view-restyle, 05-operator-console-restyle

**Status:** ready-for-agent

- [ ] Test parses token values from the global stylesheet, not a copy
- [ ] Body/reading pairs ≥ 4.5:1 (ink, body, dim, mute, read on sand surfaces; brand-ink on brand; state inks over composited state backgrounds)
- [ ] Large-text and UI pairs ≥ 3:1
- [ ] Suite fails if a token is nudged below threshold (spot-check by temporarily changing a value)
- [ ] All tests, lint, and `tsc -b` build pass
