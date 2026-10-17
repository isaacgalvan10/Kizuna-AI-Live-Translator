# 01: Theme foundation — tokens, shell wash, fonts

**What to build:** The whole app stands on the new Kizuna identity, with behaviour and structure untouched. The global stylesheet's scaffold leftovers (fixed-width root with side borders, scaffold typography, undesigned dark block) are gone, replaced by a Tailwind v4 `@theme` token block carrying the settled palette from the design doc: sand surface steps (base → panel → card → raise → deep), quiet border tones, the ink/body/dim/mute/read text hierarchy, evergreen brand + deep + ink, state colours (live emerald with text-safe ink, paused amber, danger rose, stopped grey), the primary button gradient, chrome/reading font families, and the two warm shadows. The blur-blob background in the app shell becomes one static, very subtle wash — no animation, no blur. Noto Sans JP (chrome) and Noto Serif JP (reading) load from Google Fonts with CJK-safe fallback stacks, so every script renders while fonts load and the arrangement survives offline.

Notes for the implementer:

- The token values in `docs/ui-redesign-design.md` and the prototype's stylesheet (`docs/ui-redesign-visual.html`) are authoritative — do not invent palette values, and do not restyle any view component in this ticket.
- Expose tokens under names that read naturally as Tailwind utilities and cannot collide with built-ins (e.g. avoid `--color-base`, since `text-base` is a font-size utility). Surface steps as a `sand-*` family are a safe default.
- Fonts: subset families only, `display=swap`, preconnect; preload only what the Listener View needs.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] Scaffold leftovers removed from the global stylesheet; `@theme` token block added covering every category in the design doc token table
- [x] Tailwind utilities generated for the token set (backgrounds, borders, text, shadows, fonts) and verified in use
- [x] App shell uses one static background wash; no `backdrop-filter` remains in it
- [x] Noto Sans JP + Noto Serif JP load with `display=swap` and CJK-safe fallback stacks (Hiragino, Yu, Malgun Gothic, Microsoft YaHei, PingFang peers)
- [x] All existing tests, lint, and `tsc -b` build pass unchanged

## Comments

- Implemented in `0cb393e` (fast-forwarded into `ui-redesign`). Later amended by ticket 06's AA token rebases (`a44f7a5`) and the review fix pass (`173a332`), which added the `waiting` and `focus` token families.
- Verification at merge: 53 frontend tests passing (was 46), `eslint .` clean, `tsc -b && vite build` clean. Final integration state: 117 tests, lint/build clean.
- Token/utility names later tickets read from `frontend/src/index.css`: sand-base/deep/panel/card/raise, line/line-soft, ink/body/dim/mute/read, brand + deep/ink/soft/wash/line/tint, btn ramp, state families live/paused/danger/stopped (plus waiting/focus post-review), shadow-float/shadow-qr, font-serif/sans/mono (CJK fallbacks inside the font tokens).
- Fonts load via one Google Fonts css2 request with preconnect + `display=swap`.
