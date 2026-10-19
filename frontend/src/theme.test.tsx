import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import App from './App';
import css from './index.css?raw';
import html from '../index.html?raw';

// The global stylesheet and the document shell are shipped artifacts in their
// own right: the @theme token block is the single source of truth every view
// consumes, and index.html owns the webfont loading. Vite's ?raw imports hand
// the tests the exact shipped bytes.

function themeBlock(): string {
  const block = css.match(/@theme\s*\{([^}]*)\}/);
  if (!block) {
    throw new Error('index.css has no @theme block');
  }
  return block[1];
}

const COLOUR_TOKENS = [
  // sand surface steps (page base up to raised controls)
  '--color-sand-base',
  '--color-sand-deep',
  '--color-sand-panel',
  '--color-sand-card',
  '--color-sand-raise',
  // borders
  '--color-line',
  '--color-line-soft',
  // text hierarchy
  '--color-ink',
  '--color-body',
  '--color-dim',
  '--color-mute',
  '--color-read',
  // brand evergreen
  '--color-brand',
  '--color-brand-deep',
  '--color-brand-ink',
  '--color-brand-soft',
  '--color-brand-wash',
  '--color-brand-line',
  '--color-brand-tint',
  // keyboard focus indicator
  '--color-focus',
  // primary action button
  '--color-btn',
  '--color-btn-deep',
  '--color-btn-border',
  '--color-btn-ink',
  // live feed states (waiting is the listener's pre-service state)
  '--color-waiting',
  '--color-waiting-ink',
  '--color-waiting-soft',
  '--color-waiting-line',
  '--color-live',
  '--color-live-ink',
  '--color-live-soft',
  '--color-live-line',
  '--color-paused',
  '--color-paused-ink',
  '--color-paused-soft',
  '--color-paused-line',
  '--color-danger',
  '--color-danger-ink',
  '--color-danger-soft',
  '--color-danger-line',
  '--color-stopped',
  '--color-stopped-ink',
  '--color-stopped-soft',
  '--color-stopped-line',
];

describe('the global stylesheet defines the settled theme', () => {
  it('declares every Kizuna colour token inside @theme as a literal colour', () => {
    const theme = themeBlock();
    for (const token of COLOUR_TOKENS) {
      expect(theme, `${token} missing from @theme`).toMatch(
        new RegExp(`${token}:\\s*(#[0-9A-Fa-f]{3,8}|rgba?\\([^)]+\\))`)
      );
    }
  });

  it('declares the two warm shadows and the three font families', () => {
    const theme = themeBlock();
    expect(theme).toMatch(/--shadow-float:\s*[^;]+;/);
    expect(theme).toMatch(/--shadow-qr:\s*[^;]+;/);
    expect(theme).toMatch(/--font-sans:\s*"Noto Sans JP"/);
    expect(theme).toMatch(/--font-serif:\s*"Noto Serif JP"/);
    expect(theme).toMatch(/--font-mono:\s*[^;]+;/);
  });

  it('gives chrome and reading stacks CJK-safe fallbacks', () => {
    const theme = themeBlock();
    const sans = theme.match(/--font-sans:\s*([^;]+);/)?.[1] ?? '';
    const serif = theme.match(/--font-serif:\s*([^;]+);/)?.[1] ?? '';
    for (const face of [
      'Hiragino Kaku Gothic ProN',
      'Yu Gothic UI',
      'Malgun Gothic',
      'Microsoft YaHei',
      'PingFang SC',
    ]) {
      expect(sans, `sans stack is missing ${face}`).toContain(face);
    }
    for (const face of ['Hiragino Mincho ProN', 'Yu Mincho', 'Source Han Serif JP', 'Nanum Myeongjo', 'Songti SC']) {
      expect(serif, `serif stack is missing ${face}`).toContain(face);
    }
  });

  it('drops the Vite scaffold leftovers', () => {
    expect(css).not.toMatch(/#root\s*\{/);
    expect(css).not.toMatch(/1126px/);
    expect(css).not.toMatch(/prefers-color-scheme/);
    expect(css).not.toMatch(/aa3bff/);
    expect(css).not.toMatch(/@tailwind\s+(base|components|utilities)/);
  });
});

describe('the document shell loads the Kizuna webfonts', () => {
  it('preconnects to both Google Fonts origins', () => {
    expect(html).toMatch(
      /<link rel="preconnect" href="https:\/\/fonts\.googleapis\.com"\s*\/?>/
    );
    expect(html).toMatch(
      /<link rel="preconnect" href="https:\/\/fonts\.gstatic\.com" crossorigin\s*\/?>/
    );
  });

  it('requests Noto Sans JP and Noto Serif JP with display=swap', () => {
    const href = html.match(/href="(https:\/\/fonts\.googleapis\.com\/css2[^"]*)"/)?.[1];
    expect(href).toBeDefined();
    expect(href).toContain('family=Noto+Sans+JP');
    expect(href).toContain('family=Noto+Serif+JP');
    expect(href).toContain('display=swap');
  });
});

describe('the document is pinned to the settled light theme', () => {
  it('opts out of browser auto-dark with an only-light meta tag', () => {
    expect(html).toMatch(/<meta name="color-scheme" content="only light"\s*\/?>/);
  });

  it('declares color-scheme: only light on the root', () => {
    expect(css).toMatch(/color-scheme:\s*only light;/);
  });

  it('tints the phone browser chrome with the sand base', () => {
    expect(html).toMatch(/<meta name="theme-color" content="#F0E7D0"\s*\/?>/i);
  });
});

describe('the app shell', () => {
  it('renders one static background wash instead of blur blobs', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    expect(container.querySelectorAll('[class*="blur-3xl"]')).toHaveLength(0);

    const wash = screen.getByTestId('app-background');
    expect(wash).toHaveAttribute('aria-hidden', 'true');
    expect(wash.childElementCount).toBe(0);
    expect(wash.className).not.toMatch(/blur|backdrop|animate/);
  });
});
