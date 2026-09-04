import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = "http://127.0.0.1:8088";

export default defineConfig({
  plugins: [react()],
  // Write the frozen bundle directly into frontend/dist (served by FastAPI).
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/repos": backend,
      "/history": backend,
      "/timeline": backend,
      "/commit": backend,
      "/refs": backend,
      "/api": backend,
      "/events": { target: backend, ws: true },
    },
  },
});
