import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, "/");

          if (normalized.indexOf("/node_modules/") === -1) {
            return;
          }

          if (
            normalized.indexOf("/react/") >= 0 ||
            normalized.indexOf("/react-dom/") >= 0 ||
            normalized.indexOf("/react-router-dom/") >= 0 ||
            normalized.indexOf("/@tanstack/react-query/") >= 0 ||
            normalized.indexOf("/axios/") >= 0 ||
            normalized.indexOf("/zustand/") >= 0 ||
            normalized.indexOf("/sonner/") >= 0 ||
            normalized.indexOf("/lucide-react/") >= 0 ||
            normalized.indexOf("/clsx/") >= 0 ||
            normalized.indexOf("/tailwind-merge/") >= 0
          ) {
            return "app-vendor";
          }

          if (
            normalized.indexOf("/echarts/") >= 0 ||
            normalized.indexOf("/zrender/") >= 0 ||
            normalized.indexOf("/echarts-for-react/") >= 0
          ) {
            return "analytics-vendor";
          }

          if (normalized.indexOf("/@tanstack/react-table/") >= 0) {
            return "analytics-table";
          }
        },
      },
    },
  },
  server: {
    port: 5173
  }
});
