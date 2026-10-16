// WebSocket connections ride the page's own origin so phones on the LAN can
// reach them: in dev, Vite proxies /ws to the backend (see vite.config.ts).
// VITE_WS_ORIGIN overrides this for split deployments.
export const WS_ORIGIN =
  import.meta.env.VITE_WS_ORIGIN ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
