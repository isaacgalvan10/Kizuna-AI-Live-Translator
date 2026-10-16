# Kizuna UI redesign — palette and surfaces

This grill settles Kizuna's visual identity. The white glassmorphic look — translucent cards over blurred pastel blobs — is replaced by a light-first, deep and colourful design: a warm sand-toned base with deep evergreen accents, solid layered surfaces (no backdrop blur anywhere), and serif reading text over sans chrome. Feed states keep their own colours (emerald live, amber paused, rose stop) and visibly outrank the brand palette. The settled prototype is exported at `docs/ui-redesign-visual.html`; build from it together with the token table below.

## Terms

- **Surface** — A layer of the UI's background (page base, panel, card, raised control) that expresses depth through tone and border rather than blur. _Avoid_: material, layer
- **Glassmorphism** — The card treatment being removed: translucent white panels with backdrop blur over blurred colour blobs. _Avoid_: frosted glass, acrylic
- **State colours** — The emerald/amber/rose (plus grey) trio that encodes live/paused/stopped/ended; they outrank the brand palette wherever feed state is shown. _Avoid_: status colours, badges
- **Reading measure** — The maximum width of reading text (translation and transcript): about 60–75 latin characters or 35–45 CJK characters per line. _Avoid_: max-width, container width

## Why

The user's words: "I don't like the current colors, glassmorphism and design, its a little too white and bland. Help me come up with a better modern design, and color scheme."

What exists today: white-glass cards (`bg-white/80 backdrop-blur-xl`) repeated across all three components, three blurred pastel blobs (indigo/violet/amber) behind every screen (`frontend/src/App.tsx:8-13`), indigo-gradient buttons, slate text — four blur layers deep — plus Vite scaffold leftovers in `index.css` (fixed-width `#root`, an undesigned `prefers-color-scheme: dark` block). The app is used on phones by guests in a dim sanctuary and by the operator at a laptop; the redesign had to answer the blandness without losing the calm the reading experience needs.

## Locked decisions

**Base mode: light-first, deep and colourful (q1 → C).** Every surface carries pigment; there is no plain white page anywhere. Rejected: dark-only (the grill's initial recommendation; retired after the user saw the v1 dark cut — a light, warm depth was wanted instead), system-aware light + dark (double the design surface, two themes, diluted identity), role-split dark guest / light operator (two identities for one brand).

**Palette: deep evergreen + warm sand (q2 → C).** Sand-toned pigmented bases with deep evergreen accents and warm neutrals. Rejected: washi + kintsugi gold (the recommendation; strong Japanese material story, but evergreen won on taste), midnight indigo + violet (safe continuity, reads like every blue-violet SaaS product), aubergine + apricot (the boldest taste call, too risky).

**Surfaces: solid layered (q3 → A).** Cards are solid tones stepping up the sand family (base → panel → card → raise), separated by 1px warm borders; shadows appear only on genuinely floating elements (status pills, the QR card). No `backdrop-filter` anywhere. Rejected: flat hairline (no elevation makes floating elements impossible), a whisper of glass in chrome (user rejected glassmorphism outright), pronounced depth (heavy shadows fight the reading calm).

**Scope: reskin + light structural tuning (q4 → B).** All three views keep their structures — the two-panel listener grid, the operator's control stack, the picker card. Restyle everything; refine within the structure only. Existing tests pin the DOM (`data-testid` panels and scroll containers), so structural re-architecture is out. Rejected: reskin only (too little for "modern"), full redesign (re-opens the test surface and risks the calm).

**State colours outrank the brand (locked from feedback).** The LIVE pill stays emerald and pulsing, and the operator's Start button stays emerald green, even though the brand is evergreen — a feed state must never be mistaken for brand decoration. Kept distinct by tone (state emerald `#10B981` vs brand pine `#1E6248`), by the pulsing dot, and never by colour alone (pills carry text labels).

## Routine choices

- **Type: serif content + sans chrome (q5 → A).** Noto Serif JP for translation and transcript reading lines (≥18px); Noto Sans JP for chrome, controls, and labels; CJK-safe fallback stacks (Hiragino, Yu Mincho, Malgun Gothic, Microsoft YaHei, PingFang; see tokens). Load subset families only; preload only what the listener view needs.
- **Listener tuning: chrome + reading polish (q6 → B).** Quieter app header, a real reading measure, the interim (in-progress) line as a distinct breathing pulse, the translation typeset like text. No layout re-architecture.
- **Flowing-text reading style (locked from feedback).** Translation lines render as sentences/short paragraphs with space between them — no per-line boxes. The Japanese transcript panel keeps the same treatment so both panels read as text.
- **One background gesture.** A single static, very subtle background wash replaces the three blurred blobs; nothing animated.
- **QR card stays white.** Scanner and print reliability beat palette purity: the QR panel keeps its white quiet zone, with a heavier warm shadow (`--shadow-qr`).
- **The visual pins a concrete token set** — the implementation starting point:

| Token | Value | Use |
|---|---|---|
| `--base` | `#F0E7D0` | Page base (sand) |
| `--deep` | `#E7DCC0` | Deeper sand areas |
| `--panel` \| `--card` \| `--raise` | `#F3ECD9` \| `#F7F1E0` \| `#FBF6EA` | The layered surface steps |
| `--line` \| `--line-soft` | `#DCCEAE` \| `#E7DCC2` | Borders |
| `--ink-900` | `#1E3B2C` | Headings (evergreen ink) |
| `--text` \| `--text-dim` \| `--text-mute` \| `--read` | `#4C4A36` \| `#6E6B52` \| `#8C8869` \| `#3E3A28` | Text hierarchy; `--read` for reading lines |
| `--brand` \| `--brand-deep` \| `--brand-ink` | `#1E6248` \| `#174D39` \| `#F2EDDC` | Brand evergreen; text on brand |
| `--btn-grad` \| `--btn-border` | `linear-gradient(180deg,#257357,#1B5A43)` \| `#174D39` | Primary buttons |
| `--emerald` (+ `#07714B` text) | `#10B981` | LIVE state |
| `--amber` | `#D9880A` | Paused state |
| `--rose` | `#E0486B` | Stop / error state |
| grey `#7A7260` family | — | Stopped / ended state |
| `--shadow-float` \| `--shadow-qr` | `0 6px 16px rgba(70,58,30,.16)` \| heavier warm | Floating elements; QR card |

(The prototype's `--board-*` tokens are its own gallery chrome, not app UI.)

## Verified facts

- Stack: React 19 + Vite + Tailwind CSS v4 (`@tailwindcss/vite`) — CSS-first config via `@theme`; there is no `tailwind.config.js`.
- Components: `GuestLanding.tsx` (QR join + language picker), `Listener.tsx` (WebSocket transcript, auto-scroll only when near bottom, speech synthesis), `OperatorConsole.tsx` (login, Start/Pause/Stop, audio pipeline, QR via `qrcode.react`).
- Current styling is duplicated per component; the state pill maps (`FEED_STATE_UI` in `OperatorConsole.tsx:40`, `LISTENER_STATE_UI` in `Listener.tsx:24`) are the natural home for the new state tokens.
- `Listener.test.tsx`, `OperatorConsole.test.tsx`, `GuestLanding.test.tsx` pin current DOM and behaviour — treat the structure as frozen per q4.
- `index.css` scaffold leftovers (`#root` fixed at 1126px with vertical borders, h1/h2 sizes, the undesigned dark block) must be cleaned up or they will fight the full-bleed sand background.
- Design research (ui-ux-pro-max) supplied the calm-palette and Noto pairing candidates and the accessibility checklist; the frontend-design guidance shaped the restraint rules (no gradient text, one orchestrated background gesture, no template tells).

## Risks

- **CJK serif rendering**: Noto Serif JP looks heavier at small sizes — hold reading lines at 18px+, verify on real phones (iOS Safari, Android Chrome), fall back to sans if legibility suffers.
- **Font loading**: subset and preload; first paint falls back to system CJK faces — verify no layout jump on the listener screen.
- **Brightness in a dim sanctuary**: light-first was the user's call; the sand base (never `#fff`) and the subtle wash mitigate glare, but judge it in an evening service.
- **State vs brand green proximity**: mitigated (tone, pulse, labels) but keep checking at a glance on cheap screens.
- **Contrast**: every text-on-sand and text-on-evergreen pair needs an AA check at implementation — the tokens were drawn for it, but verify.
- **Tailwind v4**: theme tokens belong in `@theme` inside `index.css`; don't invent a JS config that doesn't exist.

## Deferred

- **Collapsible Japanese transcript footer on phones** (q6 option C): revisit if phone layouts feel cramped in a real service; would re-open the listener structure and its tests.
- **Dark theme**: out after q1 → C; reopens only if glare becomes a real complaint.
- **Full structural redesign** of listener/operator (q4 option C): a per-view future ticket if ever needed.
- **Alternative palettes** (washi + gold, indigo + violet, aubergine + apricot): reference only; could return as a seasonal or print identity.

## Open threads

None — every discussion ended in a decision or a deferral.
