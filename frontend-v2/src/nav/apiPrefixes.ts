// API path prefixes served by the backend. Must match the regex in frontend/Caddyfile, so dev
// (Vite proxy) and production (Caddy) route the same paths to the API.
export const API_PREFIX_RE =
  "^/(health|training|body|admin|sync|activities|assessments|export|nutrition|docs|openapi\\.json)(/.*)?$"
