/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useState, useEffect } from 'react';
import api from '@/services/api.service';
import type { VizData } from '@/types/api';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export type VizTab = 'distribution' | 'correlation' | 'categorical';

/* ─── Hook ───────────────────────────────────────────────────────────────────────────────── */

export function useViz(sessionId: string) {
  const [data, setData] = useState<VizData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<VizTab>('distribution');

  const [varX, setVarX] = useState<string>('');
  const [varY, setVarY] = useState<string>('');
  const [selectedCatCol, setSelectedCatCol] = useState<string>('');

  useEffect(() => {
    if (!sessionId) return;

    api
      .get<VizData>(`/api/viz/${sessionId}`)
      .then((res) => {
        setData(res.data);

        if (res.data?.columns?.length === 0 && res.data?.categorical_data?.length > 0) {
          setActiveTab('categorical');
        }

        if (res.data?.columns?.length >= 2) {
          setVarX(res.data.columns[0]);
          setVarY(res.data.columns[1]);
        }

        if (res.data?.categorical_data?.length > 0) {
          setSelectedCatCol(res.data.categorical_data[0].column);
        }

        setIsLoading(false);
      })
      .catch((err) => {
        setErrorMsg(
          err.response?.data?.error ||
          err.response?.data?.detail ||
          'Failed to load visualization data.'
        );
        setIsLoading(false);
      });
  }, [sessionId]);

  return {
    data,
    isLoading,
    errorMsg,
    activeTab,
    setActiveTab,
    varX,
    setVarX,
    varY,
    setVarY,
    selectedCatCol,
    setSelectedCatCol,
  };
}
