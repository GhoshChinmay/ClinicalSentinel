import axios from "axios";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE,
});

// ---------------------------------------------------------------------------
// API key interceptor — when NEXT_PUBLIC_API_KEY is set, attach it to every
// outgoing request as an X-API-Key header.  When it is NOT set (local dev
// without auth), no header is added and the backend allows all requests.
// ---------------------------------------------------------------------------
const apiKey = process.env.NEXT_PUBLIC_API_KEY;

if (apiKey) {
  api.interceptors.request.use((config) => {
    config.headers = config.headers ?? {};
    config.headers["X-API-Key"] = apiKey;
    return config;
  });
}

export default api;
