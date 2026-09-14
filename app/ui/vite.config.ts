import { defineConfig } from "vite";

// In development Vite serves the interface with hot reload, and the WebSocket goes to the Python process
// started with --port 8750. Once built, the Python server serves it.
export default defineConfig({
  server: {
    proxy: {
      "/ws": { target: "ws://127.0.0.1:8750", ws: true },
    },
  },
});
