// バックエンドの接続先はここだけで決める。変えるときは .env.local などで VITE_API_BASE を指定する。
// uvicorn は 127.0.0.1 で待ち受けるので、localhost (IPv6 の ::1 に解決されることがある) ではなくこちらを既定にする。
const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export const apiUrl = (path: string): string => `${API_BASE}${path}`;

export const wsUrl = (path: string): string => apiUrl(path).replace(/^http/, "ws");
