import axios from "axios";

// Relative URLs keep every request on the page's own origin. In dev, Vite
// proxies /api to the backend (see vite.config.ts), so a guest who loads the
// app from the LAN IP reaches the backend through the same host — no CORS and
// no hardcoded hostnames. VITE_API_ORIGIN overrides this for split deployments.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_ORIGIN || "",
});

export default api;
