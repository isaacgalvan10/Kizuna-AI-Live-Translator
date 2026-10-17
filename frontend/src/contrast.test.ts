import { describe, expect, it } from 'vitest';
import css from './index.css?raw';
import { FEED_BUTTON_RAMPS } from './feedStateVisuals';

// The @theme block in index.css is the single source of truth for every colour
// in the app (theme.test.tsx guards its shape; this suite guards its WCAG
// contrast promise). Values are parsed here, never copied: a palette tweak that
// breaks accessibility fails CI instead of shipping.
//
// Method: WCAG 2.2 relative luminance on sRGB channels, with translucent fills
// alpha-composited over their actual backdrop first (plain sRGB compositing,
// the maths behind rgba() backgrounds). Because a soft state fill changes with
// the surface under it, every stressed pair is measured on each surface it can
// really sit on.

interface Rgba {
  r: number;
  g: number;
  b: number;
  a: number;
}

const THEME: Map<string, string> = (() => {
  const block = css.match(/@theme\s*\{([^}]*)\}/)?.[1];
  if (!block) throw new Error('index.css has no @theme block');
  const tokens = new Map<string, string>();
  for (const [, name, value] of block.matchAll(/(--color-[\w-]+):\s*([^;]+);/g)) {
    tokens.set(name, value.trim());
  }
  if (tokens.size === 0) throw new Error('index.css @theme declares no --color-* tokens');
  return tokens;
})();

function parseColour(raw: string): Rgba {
  const short = raw.match(/^#([0-9a-fA-F]{3})$/);
  if (short) {
    const pair = (i: number) => parseInt(short[1][i].repeat(2), 16);
    return { r: pair(0), g: pair(1), b: pair(2), a: 1 };
  }
  const full = raw.match(/^#([0-9a-fA-F]{6})$/);
  if (full) {
    const digits = full[1];
    return {
      r: parseInt(digits.slice(0, 2), 16),
      g: parseInt(digits.slice(2, 4), 16),
      b: parseInt(digits.slice(4, 6), 16),
      a: 1,
    };
  }
  const rgba = raw.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (rgba) {
    return { r: Number(rgba[1]), g: Number(rgba[2]), b: Number(rgba[3]), a: rgba[4] === undefined ? 1 : Number(rgba[4]) };
  }
  throw new Error(`cannot parse colour token value: ${raw}`);
}

function token(name: string): Rgba {
  const raw = THEME.get(name);
  if (raw === undefined) throw new Error(`${name} is not declared in the index.css @theme block`);
  return parseColour(raw);
}

// Alpha compositing of foreground over an opaque backdrop, in sRGB space.
function over(fg: Rgba, bg: Rgba): Rgba {
  return {
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  };
}

function linearise(channel: number): number {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(colour: Rgba): number {
  return (
    0.2126 * linearise(colour.r) +
    0.7152 * linearise(colour.g) +
    0.0722 * linearise(colour.b)
  );
}

function contrast(a: Rgba, b: Rgba): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

// The three sand surfaces the app's text really sits on: the page base, panel
// surfaces, and card surfaces (the language-picker card, the console card).
const SAND_SURFACES = ['--color-sand-base', '--color-sand-panel', '--color-sand-card'] as const;
const BODY_TEXT = ['--color-ink', '--color-read', '--color-body', '--color-dim'] as const;

describe('body and reading text clears AA 4.5:1 on every sand surface', () => {
  it.each(
    BODY_TEXT.flatMap((text) =>
      SAND_SURFACES.map((surface) => ({ text, surface }))
    )
  )('$text on $surface', ({ text, surface }) => {
    const ratio = contrast(token(text), token(surface));
    expect(ratio, `${text} on ${surface} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
  });
});

describe('text on the brand and button ramps clears AA 4.5:1', () => {
  it('--color-brand-ink on --color-brand', () => {
    const ratio = contrast(token('--color-brand-ink'), token('--color-brand'));
    expect(ratio, `brand-ink on brand is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
  });

  it.each([{ stop: '--color-btn' }, { stop: '--color-btn-deep' }])(
    '--color-btn-ink on the $stop stop',
    ({ stop }) => {
      const ratio = contrast(token('--color-btn-ink'), token(stop));
      expect(ratio, `btn-ink on ${stop} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
    }
  );
});

// The feed buttons label themselves with --color-btn-ink at 21px/font-extrabold
// — WCAG large text (>=14pt bold), so AA asks 3:1 here, not 4.5:1. 4.5:1 is
// unsatisfiable on the settled state ramps without abandoning the locked "state
// colours outrank the brand" look: no ink colour clears every stop — even pure
// black only reaches 4.47:1 on danger's rose top and 3.34:1 on its deep stop,
// while pure white reaches only 2.70:1 on the live top. The suite therefore
// enforces the normative large-text threshold on the real button ink (pinned by
// OperatorConsole.test.tsx: 'text-btn-ink'), on both stops of every ramp.
//
// The ramp classes are owned by feedStateVisuals.ts (FEED_BUTTON_RAMPS), the
// same data the console renders; each `from-`/`to-` utility is mapped back to
// the `--color-*` token it must name, so a ramp can never point at a colour
// this suite does not measure.
const RAMP_STOPS = Object.entries(FEED_BUTTON_RAMPS).flatMap(([state, ramp]) =>
  [ramp.from, ramp.to].map((utility) => ({
    state,
    stop: `--color-${utility.replace(/^(?:from|to)-/, '')}`,
  }))
);

describe('feed button labels clear AA 3:1 (large text) on both gradient stops', () => {
  it.each(RAMP_STOPS)('--color-btn-ink on the $state ramp at $stop', ({ stop }) => {
    const ratio = contrast(token('--color-btn-ink'), token(stop));
    expect(ratio, `btn-ink on ${stop} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(3);
  });
});

// The state pill text sits on a translucent soft fill; the fill's real colour
// depends on the surface under it. The listener pill and banners sit on the
// page base, the console pill and the guest notices on card surfaces — so each
// pair must clear 4.5:1 on both, worst case winning.
const STATE_PILLS = [
  { ink: '--color-live-ink', soft: '--color-live-soft' },
  { ink: '--color-paused-ink', soft: '--color-paused-soft' },
  { ink: '--color-danger-ink', soft: '--color-danger-soft' },
  { ink: '--color-stopped-ink', soft: '--color-stopped-soft' },
  { ink: '--color-waiting-ink', soft: '--color-waiting-soft' },
] as const;
const PILL_BACKDROPS = ['--color-sand-base', '--color-sand-card'] as const;

describe('state pill and banner text clears AA 4.5:1 over its composited fill', () => {
  it.each(
    STATE_PILLS.flatMap(({ ink, soft }) =>
      PILL_BACKDROPS.map((surface) => ({ ink, soft, surface }))
    )
  )('$ink over $soft composited on $surface', ({ ink, soft, surface }) => {
    const ratio = contrast(token(ink), over(token(soft), token(surface)));
    expect(ratio, `${ink} over ${soft} on ${surface} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
  });
});

describe('non-text UI boundaries clear AA 3:1', () => {
  it.each([{ surface: '--color-sand-base' }, { surface: '--color-sand-card' }])(
    'the primary button border --color-btn-border against $surface',
    ({ surface }) => {
      const ratio = contrast(token('--color-btn-border'), token(surface));
      expect(ratio, `btn-border against ${surface} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(3);
    }
  );

  // The one keyboard focus indicator (--color-focus, the brand evergreen at an
  // alpha that clears 3:1) is consumed by the guest language buttons and every
  // operator control. Offset 2px, it composites over the surface behind the
  // control: the card (guest picker, login card) or the console's control panel.
  it.each([{ surface: '--color-sand-card' }, { surface: '--color-sand-panel' }])(
    'the focus indicator --color-focus against $surface',
    ({ surface }) => {
      const ring = over(token('--color-focus'), token(surface));
      const ratio = contrast(ring, token(surface));
      expect(ratio, `--color-focus on ${surface} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(3);
    }
  );
});

// Inventory of pairs deliberately NOT asserted, with the ratios this suite's
// maths computes (kept as a comment: no assertion, so a future palette tweak
// moves the numbers, not CI). The rule applied: WCAG 1.4.11 covers information
// needed to identify a control; where a text label already carries the meaning,
// the colour reinforcement is decorative and re-asserting it would fight the
// settled look for none of the accessibility.
//
// State dots on their own soft fill over the base (decorative — the pill label
// carries the state):
//   live    #10B981 over live-soft        1.81:1
//   paused  #D9880A over paused-soft      2.04:1
//   stopped #9A9078 over stopped-soft     2.29:1
//   waiting #B1A88F over waiting-soft     1.76:1
// State pill 1px borders over their soft fill (the fill and the label already
// mark the pill boundary):
//   live-line    2.40:1   paused-line   2.04:1
//   danger-line  3.25:1   stopped-line  3.66:1
//   waiting-line 1.28:1 (the muted Waiting pill is deliberately the softest)
// The feed buttons carry no border (FEED_BUTTON in OperatorConsole.tsx has none,
// and @theme declares no state-button border token), so the arbited "state
// button borders" UI pair has no token to measure; if a border is ever added,
// add the 3:1 assertion with it.
// --color-mute is used only on disabled controls (disabled:text-mute) — WCAG
// exempts inactive components: on sand-base 2.92:1, on sand-card 3.19:1.
// Known non-required text pairs for the record:
//   dim on sand-deep (the Room # badge)      4.14:1
// Every keyboard-focusable control (the guest language buttons and all operator
// inputs and buttons) now carries the single --color-focus outline asserted
// above; the previous weak operator treatment (ring-brand-wash, ~1.25:1) is
// gone with it.
