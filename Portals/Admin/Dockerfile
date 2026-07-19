# syntax=docker/dockerfile:1

# ---------- Stage 1: build the Angular app ----------
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies against the lockfile for reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci

# Build the production bundle.
COPY . .
RUN npm run build

# ---------- Stage 2: serve the static bundle via nginx ----------
FROM nginx:1.27-alpine AS runtime

# SPA routing: fall back to index.html for client-side routes.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Angular 20 emits the app under dist/<project-name>/browser.
COPY --from=build /app/dist/admin/browser /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
