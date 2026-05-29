FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
# adapter-cloudflare outputs _worker.js based format
# for Docker/nginx, generate static fallback via adapter-static
# keep this Dockerfile for server2: switch to adapter-static locally if needed
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
