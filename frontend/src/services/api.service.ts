/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import axios from 'axios';

import { API_BASE, API_KEY } from '@/constants/config';

/* ─── Config ─────────────────────────────────────────────────────────────────────────────── */

const api = axios.create({
  baseURL: API_BASE,
});

if (API_KEY) {
  api.interceptors.request.use((config) => {
    config.headers = config.headers ?? {};
    config.headers['X-API-Key'] = API_KEY;
    return config;
  });
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */

/**
 * Pre-configured Axios instance for backend communications.
 * Automatically injects the API key if present in the environment configuration.
 */
export default api;
