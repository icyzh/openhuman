# Multi-stage Dockerfile for Next.js in Turborepo using Bun
FROM oven/bun:1.1-alpine AS base

# Install compatibility libraries
RUN apk add --no-cache libc6-compat

# 1. Prune step
FROM base AS pruner
WORKDIR /app
RUN bun add -g turbo
COPY . .
RUN turbo prune @openhuman/web --out=out

# 2. Installer step
FROM base AS installer
WORKDIR /app

# Copy pruned lockfile and package definitions
COPY --from=pruner /app/out/json/ .
COPY --from=pruner /app/out/bun.lock ./bun.lock

# Install dependencies (including workspace packages)
RUN bun install --frozen-lockfile

# Copy source code and build
COPY --from=pruner /app/out/full/ .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Run build via Turborepo to ensure dependency builds (like api-client) are run first
RUN bun run build

# 3. Runner step
FROM base AS runner
WORKDIR /app

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy standalone build and public static files
COPY --from=installer /app/apps/web/public ./apps/web/public
COPY --from=installer --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=installer --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "apps/web/server.js"]
