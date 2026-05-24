# ── Stage 1: 빌드 ──────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# VITE_API_BASE='' → 빌드 결과물이 상대경로 /api/ 를 사용
# nginx가 /api/ 를 backend 로 프록시함
ARG VITE_API_BASE=""
RUN VITE_API_BASE=${VITE_API_BASE} npm run build

# ── Stage 2: nginx 서빙 ─────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
