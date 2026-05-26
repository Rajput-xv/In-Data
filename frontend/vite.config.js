import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Vite picks up .env.* via import.meta.env automatically.
// We bind to 0.0.0.0 so `npm run dev` works from WSL / Docker too.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
