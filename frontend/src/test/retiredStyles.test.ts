import { describe, expect, it } from 'vitest';
import { classNamesOf, retiredStyleViolations } from './retiredStyles';

// The shared guard rail every view suite uses to pin the redesign: glass blur,
// the retired palette and raw white must never come back. Its one deliberate
// exception — the operator QR card's white quiet zone — is an explicit
// allowance at the operator call site; these tests pin the mechanics.

function tree(html: string): HTMLElement {
  const container = document.createElement('div');
  container.innerHTML = html;
  return container;
}

describe('the retired-styles guard', () => {
  it('flags every retired utility anywhere in the tree', () => {
    const container = tree(`
      <div class="backdrop-blur-xl p-4">
        <p class="text-indigo-500">indigo</p>
        <p class="bg-slate-100">slate</p>
        <p class="text-violet-600">violet</p>
        <p class="bg-rose-500">rose</p>
        <p class="border-amber-300">amber</p>
        <p class="bg-emerald-400">emerald</p>
        <p class="bg-white/80">translucent white</p>
        <p class="bg-white">raw white</p>
      </div>
    `);

    const violations = retiredStyleViolations(container);

    expect(violations).toHaveLength(9);
    expect(violations.every((v) => v.includes('still wears retired styles'))).toBe(true);
  });

  it('passes clean theme-token markup', () => {
    const container = tree(
      '<div class="bg-sand-card text-brand outline-focus"><p class="bg-live-soft">ok</p></div>'
    );

    expect(retiredStyleViolations(container)).toEqual([]);
  });

  it('suppresses exactly the allowed class and nothing else', () => {
    const container = tree(
      '<div class="rounded-xl bg-white p-3"><span class="bg-white/80">no</span></div>'
    );

    const violations = retiredStyleViolations(container, ['bg-white']);

    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('bg-white/80');
  });

  it('reads the class attribute safely from SVG elements', () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'h-4 w-4');
    expect(classNamesOf(svg)).toBe('h-4 w-4');

    const container = tree('<svg class="text-slate-400"><path class="stroke-current" /></svg>');
    const violations = retiredStyleViolations(container);
    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('text-slate-400');
  });
});
