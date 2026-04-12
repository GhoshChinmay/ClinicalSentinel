/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useState, useEffect } from 'react';
import api from '@/services/api.service';
import type { CompareResponse } from '@/types/api';

/* ─── Hook ───────────────────────────────────────────────────────────────────────────────── */

/**
 * Custom hook to fetch comparison data for a given session.
 *
 * @param {string} sessionId - The session identifier.
 * @returns {object} The comparison data, loading state, and error state.
 */
export function useCompare(sessionId: string) {
  const [data, setData] = useState<CompareResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    api.get<CompareResponse>(`/api/compare/${sessionId}`)
      .then((res) => {
        setData(res.data);
        setIsLoading(false);
      })
      .catch((err) => {
        const axiosErr = err as { response?: { data?: { error?: string; detail?: string } } };
        setErrorMsg(
          axiosErr.response?.data?.error ||
          axiosErr.response?.data?.detail ||
          'Failed to fetch comparison data.'
        );
        setIsLoading(false);
      });
  }, [sessionId]);

  return { data, isLoading, errorMsg };
}
