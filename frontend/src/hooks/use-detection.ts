/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useState, useEffect } from 'react';
import api from '@/services/api.service';
import type { AnomalyRow, DriftReport, SessionDataResponse } from '@/types/api';

/* ─── Hook ───────────────────────────────────────────────────────────────────────────────── */

/**
 * Custom hook to manage the anomaly detection data and feedback.
 *
 * @param {string} sessionId - The session identifier.
 * @returns {object} Detection state and handlers.
 */
export function useDetection(sessionId: string) {
  const [data, setData] = useState<AnomalyRow[]>([]);
  const [totalAnomalies, setTotalAnomalies] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [threshold, setThreshold] = useState<number>(0);
  const [minSliderBound, setMinSliderBound] = useState<number>(0);
  const [feedbackMap, setFeedbackMap] = useState<Record<number, 'correct' | 'incorrect'>>({});
  const [driftReport, setDriftReport] = useState<DriftReport | undefined>(undefined);
  const [recommendation, setRecommendation] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!sessionId) {
      setErrorMsg('Critical Error: Session ID is missing. Please refresh and try uploading again.');
      setIsLoading(false);
      return;
    }

    const fetchData = async () => {
      try {
        const res = await api.get<SessionDataResponse>(
          `/api/data/${sessionId}?is_cleaned=false&only_anomalies=true`
        );

        if (res.data && Array.isArray(res.data.data)) {
          setData(res.data.data);
          setTotalAnomalies(res.data.total_anomalies || 0);
          setDriftReport(res.data.drift_report);
          setRecommendation(res.data.recommendation);

          const threatScores = res.data.data
            .map((r) => r.Threat_Score)
            .filter((s) => s !== undefined && s !== null) as number[];

          if (threatScores.length > 0) {
            const lowestScore = Math.floor(Math.min(...threatScores));
            const boundedMin = Math.min(lowestScore, 99);
            setMinSliderBound(boundedMin);
            setThreshold(boundedMin);
          }
        } else {
          throw new Error('Invalid data format received from the server.');
        }
      } catch (err: unknown) {
        console.error('Failed to load anomalies', err);
        const axiosErr = err as {
          response?: { data?: { error?: string; detail?: string } };
          message?: string;
        };
        setErrorMsg(
          axiosErr.response?.data?.error ||
          axiosErr.response?.data?.detail ||
          axiosErr.message ||
          'Failed to load anomaly report.'
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [sessionId]);

  const submitFeedback = async (row: AnomalyRow, idx: number, isCorrect: boolean) => {
    try {
      await api.post('/api/feedback/', {
        session_id: sessionId,
        row_data: row,
        is_correct: isCorrect,
      });
      setFeedbackMap((prev) => ({ ...prev, [idx]: isCorrect ? 'correct' : 'incorrect' }));
    } catch (e) {
      console.error('Failed to submit feedback', e);
    }
  };

  return {
    data,
    totalAnomalies,
    isLoading,
    errorMsg,
    threshold,
    setThreshold,
    minSliderBound,
    feedbackMap,
    submitFeedback,
    driftReport,
    recommendation,
  };
}
