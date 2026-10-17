# 06: Token contrast test

**What to build:** The spec's AA promise becomes a CI check. A Vitest suite reads the `@theme` token block from the global stylesheet (single source of truth — no duplicated hex values), computes WCAG contrast ratios, and fails when a palette tweak breaks accessibility: body/reading text pairs at 4.5:1 or better, large-text/UI pairs at 3:1 or better, with translucent state backgrounds composited over the sand base before measuring. It runs against the final tokens, after every view has landed.

**Blocked by:** 01-theme-foundation, 03-guest-landing-restyle, 04-listener-view-restyle, 05-operator-console-restyle

**Status:** ready-for-agent

- [x] Test parses token values from the global stylesheet, not a copy
- [x] Body/reading pairs ≥ 4.5:1 (ink, body, dim, read on sand surfaces — `mute` exempt, disabled-controls only: see Comments; brand-ink on brand; state inks over composited state backgrounds)
- [x] Large-text and UI pairs ≥ 3:1
- [x] Suite fails if a token is nudged below threshold (spot-check by temporarily changing a value)
- [x] All tests, lint, and `tsc -b` build pass

## Comments

- Implemented in `a44f7a5`: `frontend/src/contrast.test.ts` parses every `--color-*` token from the `@theme` block (no duplicated values) and asserts WCAG ratios with sRGB alpha compositing — text pairs at 4.5:1 and UI pairs (btn-border, focus indicator) at 3:1. Mutation spot-check: reverting `dim` fails exactly its sand-base pair.
- Minimal hue-preserving rebases: `dim` #6E6B52→#6B684F (4.38→4.58), `live-ink`→#066A46 (4.32→4.75), `paused-ink`→#825405 (4.30→4.74), `stopped-ink`→#655E4E (3.46→4.66), `live-btn`→#149372 and `paused-btn`→#BD7509 (top stops to 3:1), guest focus outline 55%→70% (2.49→3.35).
- Feed-button labels are 21px extrabold — WCAG large text — hence asserted at 3:1; 4.5 is mathematically unreachable on the settled ramps (even pure black caps at 4.47 on danger's top stop) and forcing it would replace the locked bright-emerald/amber ramps.
- Deliberate deviations: `mute` is exempt from the 4.5 assertion (it styles disabled controls only; WCAG 1.4.3 exemption — forcing it darkens disabled text toward enabled-looking). State dots, 1px pill borders, and `dim` on `sand-deep` are recorded in a commented inventory with real ratios, not asserted (decorative/redundant or non-required pairs).
- Review fix pass (`173a332`): new `--color-focus` token (brand at 70%, 3.35:1 over sand-card) now owns the focus value — the focus assertion no longer reads component source — and the new `waiting` family is contrast-asserted (4.56:1 worst case). Waiting's prototype ink (#8A8270, ~2.8:1) was hue-preservingly rebased to #686150 to hold the AA promise; its dot is #B1A88F (distinct from Ended's #9A9078).
