# Vite dev server for `docker compose up`. This is a DEVELOPMENT image: it runs
# `vite dev`, not a production build. Production is Vercel, which builds from
# apps/web itself and never uses this file. See docs/deploy.md.
FROM node:20-alpine

WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install

COPY apps/web/ ./

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
