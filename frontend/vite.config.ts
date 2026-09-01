import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/repos": backend,
      "/history": backend,
      "/refs": backend,
      "/api": backend,
      "/events": { target: backend, ws: true },
    },
  },
});
