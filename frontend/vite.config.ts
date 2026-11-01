import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: "127.0.0.1",
      proxy: {
        "/api":
          env.STUDIO_API_TARGET || `http://127.0.0.1:${env.API_PORT || "8000"}`,
      },
    },
  };
});
