# syntax=docker/dockerfile:1

# Dependencies first, so editing source does not reinstall them.
FROM node:22-bookworm-slim AS dependencies

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci


FROM node:22-bookworm-slim AS builder

WORKDIR /app

COPY --from=dependencies /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build


# Runtime: the standalone server only — no npm, no source tree, no full node_modules.
FROM node:22-bookworm-slim AS web

RUN useradd --create-home --uid 1001 techscope

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder --chown=techscope:techscope /app/.next/standalone ./
COPY --from=builder --chown=techscope:techscope /app/.next/static ./.next/static
COPY --from=builder --chown=techscope:techscope /app/public ./public

USER techscope
EXPOSE 3000

CMD ["node", "server.js"]
