import { defineConfig } from "vite";

// En desarrollo la interfaz la sirve Vite con recarga en caliente, y el WebSocket va al proceso
// de Python arrancado con --puerto 8750. Compilada, la sirve el propio servidor de Python.
export default defineConfig({
  server: {
    proxy: {
      "/ws": { target: "ws://127.0.0.1:8750", ws: true },
    },
  },
});
