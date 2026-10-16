# Kizuna UI Redesign Spec

Status: ready-for-agent

## Problem Statement

Kizuna's interface looks like a generic white SaaS template rather than this church's own tool. Every view — the Language Picker a Guest sees after scanning the QR Code, the Listener View a Listener follows during the Sermon, and the Operator Console at the mixer — is built from the same translucent white "glassmorphic" cards stacked over blurred pastel blobs: four blur layers deep, plain white surfaces that glare in a dim sanctuary, faint grey text, and an indigo/violet palette that carries none of the app's identity (絆 — bond — a Japanese church in Osaka, four scripts read side by side). The faintness costs something real too: backdrop blur is expensive on the cheap phones guests actually carry, and a glowing white phone screen is disruptive to neighbours in the pew. The user's words: "it's a little too white and bland."

## Solution

A complete visual redesign of all three views, settled in a design grill and captured in the exported prototype (`docs/ui-redesign-visual.html`) and its design doc (`docs/ui-redesign-design.md`):

- **Light-first, deep and colourful**: pigmented warm-sand surfaces (never plain white), with deep evergreen as the brand accent.
- **Solid layered Surfaces** replace Glassmorphism: cards step up in tone with quiet 1px borders; no backdrop blur anywhere; shadows only on genuinely floating elements.
- **Serif reading type over sans chrome**: Translation and Japanese Transcript lines set in Noto Serif JP, controls in Noto Sans JP, with CJK-safe fallbacks.
- **Flowing-text reading style**: Translation renders as sentences/short paragraphs with space between them — no per-line boxes.
- **State colours outrank the brand**: Live stays emerald (with its pulsing dot), Paused amber, Ended grey, Waiting muted — identical in both the Listener View and the Operator Console.

Behaviour, structure, and flows are unchanged: the same three views, the same Feed Control, the same QR Code, the same reading experience — wearing Kizuna's own identity.

## User Stories

1. As a Guest, I want the Language Picker to feel like this church's own product — the 絆 brand mark and evergreen-on-sand surfaces — so that scanning the QR Code doesn't land me in a generic template.
2. As a Guest, I want the three Guest Languages (English, 한국어, 中文) offered as the clear primary action, so I can pick one in seconds.
3. As a Guest who scans before the Live Feed starts, I want a calm, legible notice that the service hasn't started, so I know to pick my language and wait on the next screen.
4. As a Guest whose QR Code is bad or whose connection fails, I want the error explained in plain words on a surface I can read, so I can ask a staff member for help.
5. As a Guest arriving from a bright narthex, I want the language buttons to be unmistakably tappable, so my first impression of the app is effortless.
6. As a Listener, I want the Translation typeset as flowing sentences with space between them, so the Sermon reads like text rather than a stack of boxes.
7. As a Listener, I want the Japanese Transcript in the same calm reading style, so the two panels read as one experience.
8. As a Listener, I want serif reading type at a comfortable size, so I can track long passages without strain.
9. As a Listener, I want a measured Reading measure, so lines do not run edge-to-edge on a wide desktop screen.
10. As a Listener, I want the in-progress line to appear as a distinct, breathing interim, so I can tell a Translation is still forming.
11. As a Listener, I want the Live Feed State — Live, Paused, Ended, Waiting — to be distinguishable by colour, label, and (for Live) a pulse, so I never have to rely on colour alone.
12. As a Listener, I want the Paused banner during Worship and the Ended banner after the service to stay obvious, so I know why the text stopped.
13. As a Listener, I want the Waiting state to read as an invitation to stay rather than an error, so I don't re-scan the QR Code.
14. As a Listener, I want the Spoken Translation toggle (Audio ON/OFF) readable and reachable in the new chrome, so headphone listening works exactly as before.
15. As a Listener in a dim sanctuary, I want the Surface to be pigmented sand rather than white, so my screen doesn't glare for me or my neighbours.
16. As a Listener on an older phone, I want smooth scrolling with no backdrop blur effects, so long Sermons don't stutter.
17. As a Listener who scrolled back to re-read a line, I want the view to leave my scroll position alone until I return to the bottom, exactly as today.
18. As a Listener on a phone, I want the Translation panel above the Japanese Transcript panel with the translation taking the larger share, exactly as today.
19. As a Listener on desktop, I want the two panels side by side, exactly as today.
20. As a Listener on slow church Wi-Fi, I want the page usable while webfonts load, so reading never waits on fonts.
21. As a Korean- or Chinese-speaking Listener, I want my script set in a typeface that covers it well, so no missing-glyph boxes ever appear.
22. As an Operator, I want the console legible at a glance from standing distance — large Feed Control buttons with unambiguous State colours.
23. As an Operator, I want Start/Resume to stay emerald green as the feed action colour, so it never blends into the evergreen brand.
24. As an Operator, I want the Live Feed State pill prominent and labelled, so I can confirm the Room is live before walking away.
25. As an Operator, I want the QR Code panel to keep its white quiet zone and heavy shadow, so printing and scanning stay reliable.
26. As an Operator, I want the login card restyled but fast to fill — email, password, one clear submit action — so service setup isn't slowed.
27. As an Operator, I want Download QR and Log out to remain obvious, so housekeeping is one click.
28. As an Operator during Worship, I want the state colours and banners to match what Listeners see on their phones, so we describe the same Live Feed State.
29. As any user, I want visible focus states and unchanged keyboard navigation, so the redesign doesn't regress accessibility.
30. As any user with reduced-motion preferences, I want pulses and transitions suppressed, so the app respects my system setting.
31. As any user, I want every text-on-surface pair to meet WCAG AA contrast, so legibility doesn't depend on good eyes or good light.
32. As a maintainer, I want the Live Feed State visuals defined in one place, so the Listener View and Operator Console can never drift apart.

## Implementation Decisions

- **Scope: reskin + light structural tuning.** All three views keep their current DOM structure, layout, and flows: the Listener View's two-panel grid (mobile stacking with translation first and a larger share; desktop side-by-side), the Operator Console's control stack, and the Language Picker's single card. Only palette, Surfaces, typography, state visuals, and within-structure polish change.
- **Three view modules are restyled**: Language Picker, Listener View, Operator Console. Copy is unchanged — every existing string ("Waiting for operator to start the feed…", "Paused — worship music", "Service ended", language labels, operator helper text, error messages) stays exactly as it is.
- **App shell**: the three blurred pastel blobs are replaced by one static, very subtle background wash. No animation, no blur.
- **Token system**: the scaffold leftovers in the global stylesheet (fixed-width root with side borders, scaffold typography sizes, the undesigned dark-mode block) are removed and replaced with a Tailwind v4 `@theme` token block. Core app-facing tokens (full set and rationale in the design doc; values below come from the prototype):

  | Token | Value | Use |
  |---|---|---|
  | `--base` / `--panel` / `--card` / `--raise` | `#F0E7D0` / `#F3ECD9` / `#F7F1E0` / `#FBF6EA` | Sand surface steps (page → raised) |
  | `--deep` / `--line` / `--line-soft` | `#E7DCC0` / `#DCCEAE` / `#E7DCC2` | Deeper sand; borders |
  | `--ink-900` / `--read` / `--text` / `--text-dim` / `--text-mute` | `#1E3B2C` / `#3E3A28` / `#4C4A36` / `#6E6B52` / `#8C8869` | Heading ink; reading text; text hierarchy |
  | `--brand` / `--brand-deep` / `--brand-ink` | `#1E6248` / `#174D39` / `#F2EDDC` | Brand evergreen and text-on-brand |
  | Primary button | `linear-gradient(180deg, #257357, #1B5A43)`, border `#174D39` | Primary actions |
  | State emerald | `#10B981`, text `#07714B` | Live |
  | State amber / rose / grey | `#D9880A` / `#E0486B` / `#7A7260` families | Paused / destructive & error / stopped & ended |
  | `--shadow-float` / `--shadow-qr` | `0 6px 16px rgba(70,58,30,.16)` / heavier warm | Floating elements; QR card |

- **Surfaces rule**: no `backdrop-filter` anywhere in content; depth comes from tone steps and 1px borders; shadows only on genuinely floating elements (state pills, QR card).
- **Typography**: Noto Serif JP for Translation and Japanese Transcript reading lines (18px minimum); Noto Sans JP for chrome, controls, and labels; CJK-safe fallback stacks (Hiragino Mincho/ProN, Yu Mincho/Gothic, Malgun Gothic, Microsoft YaHei, PingFang SC and peers). Load subset families only; preload only what the Listener View needs.
- **Reading style**: Translation and Japanese Transcript render as flowing text (sentences / short paragraphs with spacing), not per-line boxes; a Reading measure constrains reading line length.
- **State-visuals module (new)**: one shared module owns the Live Feed State presentation — label, pill styling, and dot styling per state — consumed by both the Listener View (Waiting / Live / Paused / Ended) and the Operator Console (Stopped / Live / Paused). It replaces the two maps currently duplicated inside the view components. Labels stay exactly as today, including the console's "Stopped" versus the listener's "Ended" for the same underlying state — that difference is explicit data in the module, not duplication.
- **State colours outrank the brand**: emerald Live (pulsing dot, `motion-safe`), amber Paused, rose destructive/error, grey stopped/ended — always visually distinct from brand evergreen by tone, and always accompanied by a text label so colour is never the only signal.
- **QR Code panel**: stays on a white card regardless of theme (scan/print reliability), with the heavier warm shadow.
- **No behaviour changes**: WebSocket flows, speech synthesis, auto-follow scrolling, auth, and Feed Control logic are untouched.

## Testing Decisions

- **What makes a good test**: external, user-visible behaviour only. No new assertions on exact CSS class strings beyond the layout contract that already exists (it encodes the structure-freeze decision); no snapshots; no DOM-level colour assertions (jsdom has no CSS engine).
- **Regression seam (existing, must stay green)**: the four component suites — App, Language Picker, Listener View, Operator Console — render tests using testing-library + jsdom with the `FakeWebSocket` pattern. The Listener suite's layout contract (mobile stacking order, translation's larger share, desktop grid) is the guard proving the reskin did not move structure or break behaviour.
- **New seam 1 — token contrast test**: a new Vitest suite reads the global stylesheet, extracts the `@theme` tokens, and computes WCAG contrast ratios, asserting: body/reading text pairs ≥ 4.5:1 (ink, read, text, dim on base/panel/card; brand-ink on brand; state text over its state background composited onto the base surface); large-text and UI pairs ≥ 3:1. This is the only place the AA promise can be verified in CI.
- **New seam 2 — state-visuals unit test**: every Live Feed State either view can render (Waiting, Live, Paused, Ended, Stopped) has a complete, non-empty presentation (label + pill + dot), and shared states agree between the two views. Pure data test of the new module.
- **Prior art**: `Listener.test.tsx` for the `FakeWebSocket`, role/testid query style, and existing layout class-contract assertions; `OperatorConsole.test.tsx` and `GuestLanding.test.tsx` for control-flow and routing patterns.

## Out of Scope

- Dark theme (settled against: light-first identity).
- Structural redesign — collapsible Japanese Transcript footer, re-architected operator flow (deferred; would re-open the DOM and its test contracts).
- Visual-regression or screenshot tooling (no browser E2E harness exists in the repo).
- Backend, API, WebSocket, and auth changes.
- Per-Church theming, seasonal palettes, and the rejected palette directions (washi + gold, indigo + violet, aubergine + apricot).
- New copy, new features, or new flows.
- Motion beyond the existing `motion-safe` pulse and the single static wash.

## Further Notes

- Authoritative artifacts: `docs/ui-redesign-design.md` (decisions, rejected options, risks, full token table) and `docs/ui-redesign-visual.html` (the settled prototype of all three views).
- Risks to watch during implementation: CJK serif legibility at small sizes (hold 18px+, verify on real phones), webfont loading (subset + preload; no layout jump on first paint), and a glare check during an evening service — the light-first call was explicit, with the pigmented sand base as the mitigation.
- The emerald/evergreen proximity is deliberate and constrained: emerald `#10B981` family for Live versus evergreen `#1E6248` family for brand — preserve the tone gap when tuning.
- Suggested implementation order: tokens + shell wash → state-visuals module → the three views → contrast test last, against the final tokens.
