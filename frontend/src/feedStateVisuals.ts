// One module owns how each Live Feed State looks, so the Listener View and the
// Operator Console can never drift apart. Every class here references the
// @theme tokens in index.css — no literal colours, no default-palette
// utilities — and the views supply the surrounding layout.

export type FeedState = 'live' | 'paused' | 'stopped';
// The Listener View also has a Waiting state before the day's feed starts.
export type ListenerState = 'waiting' | FeedState;

export interface FeedStateVisuals {
  label: string;
  pill: string;
  dot: string;
}

// Pill and dot presentation is shared by every view that renders a feed state;
// only the label is view-specific (the listener's "Ended" versus the
// console's "Stopped" for the same underlying state).
const SHARED_PRESENTATION: Record<FeedState, Omit<FeedStateVisuals, 'label'>> = {
  live: {
    pill: 'bg-live-soft border-live-line text-live-ink',
    dot: 'bg-live motion-safe:animate-pulse',
  },
  paused: {
    pill: 'bg-paused-soft border-paused-line text-paused-ink',
    dot: 'bg-paused',
  },
  stopped: {
    pill: 'bg-stopped-soft border-stopped-line text-stopped-ink',
    dot: 'bg-stopped',
  },
};

export const LISTENER_STATE_VISUALS: Record<ListenerState, FeedStateVisuals> = {
  // Waiting is listener-only and deliberately softer than Ended: the same grey
  // hue, but a weaker pill (softer fill and line) and a lighter dot, so a guest
  // never reads "the service is over" before it has started.
  waiting: {
    label: 'Waiting',
    pill: 'bg-waiting-soft border-waiting-line text-waiting-ink',
    dot: 'bg-waiting',
  },
  live: { label: 'Live', ...SHARED_PRESENTATION.live },
  paused: { label: 'Paused', ...SHARED_PRESENTATION.paused },
  stopped: { label: 'Ended', ...SHARED_PRESENTATION.stopped },
};

export const OPERATOR_STATE_VISUALS: Record<FeedState, FeedStateVisuals> = {
  live: { label: 'Live', ...SHARED_PRESENTATION.live },
  paused: { label: 'Paused', ...SHARED_PRESENTATION.paused },
  stopped: { label: 'Stopped', ...SHARED_PRESENTATION.stopped },
};

// The console's feed-action buttons wear their state colours: the emerald
// Start/Resume ramp, the amber Pause ramp, the rose Stop ramp. Kept as complete
// literal utilities (never composed from variables) so Tailwind's scanner still
// sees them; the contrast suite maps each back to the token it must name.
export interface FeedButtonRamp {
  from: string;
  to: string;
}

export const FEED_BUTTON_RAMPS: Record<'live' | 'paused' | 'danger', FeedButtonRamp> = {
  live: { from: 'from-live-btn', to: 'to-live-btn-deep' },
  paused: { from: 'from-paused-btn', to: 'to-paused-btn-deep' },
  danger: { from: 'from-danger-btn', to: 'to-danger-btn-deep' },
};
