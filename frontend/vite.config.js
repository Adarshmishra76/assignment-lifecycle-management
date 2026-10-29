import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base URL comes from VITE_API_BASE_URL (see .env.example).
// Backend CORS already allows http://localhost:5173.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  // `npm test` runs Vitest in a jsdom environment (no browser or API needed).
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
    css: false,
    clearMocks: true,
  },
});
