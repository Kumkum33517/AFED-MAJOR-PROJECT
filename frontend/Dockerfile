FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 5173
# vite preview serves the build and keeps the /api proxy from vite.config.ts.
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
