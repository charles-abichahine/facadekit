import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the API is proxied at /api so the browser sees one origin and CORS
// never comes into it. In production VITE_API_URL points at the deployed API.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
