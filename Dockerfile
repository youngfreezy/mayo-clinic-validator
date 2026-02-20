# ── Stage 1: Build Next.js (standalone output) ───────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend ./
# Empty string so SSE EventSource uses a relative URL — nginx proxies it
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build

# ── Stage 2: Final runtime image ─────────────────────────────────────────────
FROM python:3.11-slim

# Install Node 20, nginx, supervisord
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg nginx supervisor && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Backend source (no venv needed — system Python)
COPY backend ./backend

# Next.js standalone build + static assets
COPY --from=frontend-builder /app/.next/standalone  ./frontend/
COPY --from=frontend-builder /app/.next/static      ./frontend/.next/static

# Process manager and web server config
COPY nginx.conf       /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/app.conf

# HF Spaces requires the app to listen on 7860
EXPOSE 7860

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/app.conf"]
