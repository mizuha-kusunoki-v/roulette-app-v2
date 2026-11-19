import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // バックエンドの CORS 許可 (http://localhost:3000) に合わせる
    port: 3000,
    strictPort: true,
  },
});
