# Stage 1 — build the Vue.js app
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_URL="" means axios uses relative URLs (/health/..., /sync/..., etc.)
# The Caddy reverse proxy in stage 2 forwards those paths to the backend container.
RUN VITE_API_URL="" npm run build-only

# Stage 2 — serve with Caddy
FROM caddy:2-alpine

COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1
