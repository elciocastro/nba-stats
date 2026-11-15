import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, /api vai para a API (uvicorn na porta 8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true, proxy: { "/api": "http://localhost:8100" } },
});
