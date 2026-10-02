# Stage 1 — build the Vue.js app
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_URL="" means axios uses relative URLs (/health/..., /sync/..., etc.)
# The Caddy reverse proxy in stage 2 forwards those paths to the backend container.
RUN VITE_API_URL="" npm run build-only

# Stage 2 — serve with Caddy, as an unprivileged user (not root). It listens on
# 8080, since only root may bind a port below 1024; compose maps the host port
# to it. Caddy keeps its state in XDG data/config dirs, owned by that user.
FROM caddy:2-alpine

RUN addgroup -S -g 1000 web \
    && adduser -S -D -H -u 1000 -G web web \
    && mkdir -p /data /config \
    && chown -R web:web /data /config

COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile

USER web
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ || exit 1
