import { describe, expect, it } from 'vitest';
import { LISTENER_STATE_VISUALS, OPERATOR_STATE_VISUALS } from './feedStateVisuals';

// The module's data is itself the contract: the Listener View and Operator
// Console must never drift apart on how a Live Feed State looks. These tests
// pin the exact labels the views already ship and the theme-token-only rule.

const LISTENER_STATES = ['waiting', 'live', 'paused', 'stopped'] as const;
const OPERATOR_STATES = ['live', 'paused', 'stopped'] as const;

describe('the shared Live Feed State visuals', () => {
  it('presents every state the Listener View can render', () => {
    expect(Object.keys(LISTENER_STATE_VISUALS).sort()).toEqual([...LISTENER_STATES].sort());

    for (const state of LISTENER_STATES) {
      const visuals = LISTENER_STATE_VISUALS[state];
      expect(visuals.label, `${state} is missing its label`).toBeTruthy();
      expect(visuals.pill, `${state} is missing its pill styling`).toBeTruthy();
      expect(visuals.dot, `${state} is missing its dot styling`).toBeTruthy();
    }
  });

  it('keeps the label strings the Listener View ships today', () => {
    expect(LISTENER_STATE_VISUALS.waiting.label).toBe('Waiting');
    expect(LISTENER_STATE_VISUALS.live.label).toBe('Live');
    expect(LISTENER_STATE_VISUALS.paused.label).toBe('Paused');
    expect(LISTENER_STATE_VISUALS.stopped.label).toBe('Ended');
  });

  it('presents every state the Operator Console can render', () => {
    expect(Object.keys(OPERATOR_STATE_VISUALS).sort()).toEqual([...OPERATOR_STATES].sort());

    for (const state of OPERATOR_STATES) {
      const visuals = OPERATOR_STATE_VISUALS[state];
      expect(visuals.label, `${state} is missing its label`).toBeTruthy();
      expect(visuals.pill, `${state} is missing its pill styling`).toBeTruthy();
      expect(visuals.dot, `${state} is missing its dot styling`).toBeTruthy();
    }
  });

  it('keeps the label strings the Operator Console ships today', () => {
    expect(OPERATOR_STATE_VISUALS.live.label).toBe('Live');
    expect(OPERATOR_STATE_VISUALS.paused.label).toBe('Paused');
    expect(OPERATOR_STATE_VISUALS.stopped.label).toBe('Stopped');
  });

  it('presents shared feed states identically in both views', () => {
    expect(OPERATOR_STATE_VISUALS.live).toEqual(LISTENER_STATE_VISUALS.live);
    expect(OPERATOR_STATE_VISUALS.paused).toEqual(LISTENER_STATE_VISUALS.paused);
  });

  it('makes the listener Ended versus console Stopped label difference explicit', () => {
    expect(LISTENER_STATE_VISUALS.stopped.label).toBe('Ended');
    expect(OPERATOR_STATE_VISUALS.stopped.label).toBe('Stopped');
    expect(OPERATOR_STATE_VISUALS.stopped.pill).toBe(LISTENER_STATE_VISUALS.stopped.pill);
    expect(OPERATOR_STATE_VISUALS.stopped.dot).toBe(LISTENER_STATE_VISUALS.stopped.dot);
  });

  it('gives Waiting its own muted presentation, distinct from Ended', () => {
    expect(LISTENER_STATE_VISUALS.waiting.pill).not.toBe(LISTENER_STATE_VISUALS.stopped.pill);
    expect(LISTENER_STATE_VISUALS.waiting.dot).not.toBe(LISTENER_STATE_VISUALS.stopped.dot);
  });

  it('keeps the Live dot pulse gated behind motion-safe', () => {
    expect(LISTENER_STATE_VISUALS.live.dot).toContain('motion-safe:animate-pulse');
    expect(OPERATOR_STATE_VISUALS.live.dot).toContain('motion-safe:animate-pulse');
  });
});

// Each state draws from its own @theme token family (Waiting wears its own
// muted waiting- family, a softer grey than Ended), so no view can smuggle in
// a literal colour or a default-palette utility.
const STATE_FAMILY: Record<string, 'waiting' | 'live' | 'paused' | 'stopped'> = {
  waiting: 'waiting',
  live: 'live',
  paused: 'paused',
  stopped: 'stopped',
};

describe('the styling rule', () => {
  it('uses only theme-token utilities from the state family it presents', () => {
    const presentations = [
      ...Object.entries(LISTENER_STATE_VISUALS),
      ...Object.entries(OPERATOR_STATE_VISUALS),
    ];

    for (const [state, visuals] of presentations) {
      const family = STATE_FAMILY[state];
      for (const field of ['pill', 'dot'] as const) {
        const classes = visuals[field];

        expect(classes, `${state} ${field} uses a literal colour`).not.toMatch(
          /#[0-9A-Fa-f]{3,8}|rgba?\(|hsla?\(/
        );

        const colourUtilities =
          classes.match(
            /(?:^|\s)(?:bg|text|border|ring|from|to|via|fill|stroke|outline|shadow|accent|decoration|divide)-[^\s]+/g
          ) ?? [];
        for (const utility of colourUtilities) {
          expect(utility.trim(), `${state} ${field} must use the ${family} token family`).toMatch(
            new RegExp(`^(?:bg|text|border)-${family}(?:-(?:ink|soft|line))?$`)
          );
        }
      }
    }
  });
});
