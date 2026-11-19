import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // バックエンドの CORS 許可 (http://localhost:3000 と http://127.0.0.1:3000) に合わせる
    // IPv4 のループバックだけで待ち受ける (LAN には出さない)。既定の "localhost" は環境によって ::1 だけになり、
    // http://127.0.0.1:3000 で開けなかった。ブラウザは localhost を ::1 と 127.0.0.1 の両方で試すので、localhost でも開ける
    host: "127.0.0.1",
    port: 3000,
    strictPort: true,
  },
});
