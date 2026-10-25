FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /app
COPY components/web_ui/package.json components/web_ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY components/web_ui/ ./
RUN pnpm build

FROM nginx:1.27-alpine
COPY components/web_ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY components/web_ui/docker-entrypoint.d/40-config.sh /docker-entrypoint.d/40-config.sh
RUN chmod +x /docker-entrypoint.d/40-config.sh
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
