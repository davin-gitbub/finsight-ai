import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 8000,
    host: true,
    proxy: {
      "/api": "http://127.0.0.1:5173",
      "/ws": { target: "ws://127.0.0.1:5173", ws: true },
      "/health": "http://127.0.0.1:5173",
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
});
