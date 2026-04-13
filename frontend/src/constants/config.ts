/* ─── Config ─────────────────────────────────────────────────────────────────────────────── */

/**
 * Base URL for the backend API.
 * Defaults to localhost in development if not provided.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

/**
 * Optional API key for authenticating with the backend.
 */
export const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */

const config = {
  API_BASE,
  API_KEY,
};
export default config;
