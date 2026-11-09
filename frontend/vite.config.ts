import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api goes to FastAPI, so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  envDir: "..", // the one .env lives in the repo root
  preview: { allowedHosts: process.env.PREVIEW_ALLOWED_HOSTS?.split(",").filter(Boolean) },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET ?? "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
