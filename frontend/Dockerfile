# Stage 1: Build
FROM node:20-alpine AS builder

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .

ENV API_URL=http://backend:8000
RUN pnpm build

# Stage 2: Run
FROM node:20-alpine

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

WORKDIR /app

COPY --from=builder --chown=nextjs:nextjs /app/.next ./.next
COPY --from=builder --chown=nextjs:nextjs /app/package.json ./
COPY --from=builder --chown=nextjs:nextjs /app/pnpm-lock.yaml* ./
COPY --from=builder --chown=nextjs:nextjs /app/next.config.mjs ./
COPY --from=builder --chown=nextjs:nextjs /app/node_modules ./node_modules

USER nextjs
EXPOSE 3000

CMD ["pnpm", "start"]
