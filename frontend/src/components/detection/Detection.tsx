/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { motion } from 'framer-motion';
import {
  ShieldAlert,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Crosshair,
  Activity,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import { useDetection } from '@/hooks/use-detection';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export interface DetectionProps {
  sessionId: string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────────────────────── */

const parseShapPayload = (payload?: string): Array<{ feature: string; impact: number }> | null => {
  if (!payload) return null;
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
};

/* ─── Component ──────────────────────────────────────────────────────────────────────────── */

/**
 * Detection component to display identified anomalies and SHAP attributions.
 *
 * @param {DetectionProps} props - Properties including the session identifier.
 * @returns {React.JSX.Element} The rendered detection UI.
 */
export default function Detection({ sessionId }: DetectionProps): React.JSX.Element {
  const {
    data,
    totalAnomalies,
    isLoading,
    errorMsg,
    threshold,
    setThreshold,
    minSliderBound,
    feedbackMap,
    submitFeedback,
  } = useDetection(sessionId);

  if (isLoading) {
    return (
      <div className="w-full mt-6 flex flex-col items-center justify-center h-64 border border-neutral-800 rounded-2xl bg-[#0A0A0A]">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-neutral-500 font-medium">Processing large dataset payload...</span>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="w-full mt-6 bg-red-500/10 border border-red-900/50 p-6 rounded-2xl flex items-start text-red-400">
        <AlertCircle className="w-6 h-6 mr-3 shrink-0" />
        <div>
          <h3 className="font-bold text-lg mb-1">Detection Engine Failed</h3>
          <p className="text-sm">{errorMsg}</p>
        </div>
      </div>
    );
  }

  const displayData = data
    .filter((row) => {
      if (row.Threat_Score === undefined || row.Threat_Score === null) return true;
      return row.Threat_Score >= threshold;
    })
    .slice(0, 100);

  const hasThreatScores = data.length > 0 && data.some((r) => r.Threat_Score && r.Threat_Score > 0);

  return (
    <div className="w-full mt-6">
      <div className="flex items-center justify-between bg-neutral-900 border border-neutral-800 p-6 rounded-2xl mb-6">
        <div>
          <h3 className="text-xl font-semibold flex items-center">
            <ShieldAlert className="w-5 h-5 text-red-400 mr-2" /> Scan Complete
          </h3>
          <p className="text-sm text-neutral-400">
            Our Multi-Modal AI scanned numbers, text, and categories for errors.
          </p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-red-400">{totalAnomalies}</p>
          <p className="text-xs text-neutral-500 uppercase font-bold tracking-wider">
            Anomalies Found
          </p>
        </div>
      </div>

      {hasThreatScores && (
        <div className="mb-6 p-6 bg-[#0A0A0A] border border-neutral-800 rounded-2xl shadow-xl">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h4 className="font-bold text-white flex items-center">
                <Crosshair className="w-4 h-4 mr-2 text-blue-500" />
                Threat Score Strictness
              </h4>
              <p className="text-xs text-neutral-400 mt-1">
                Filter visible anomalies based on the Supervised Classifier&apos;s confidence score.
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-black text-blue-500">{threshold}%</span>
              <span className="text-[10px] text-neutral-500 block uppercase tracking-widest mt-1">
                Threshold
              </span>
            </div>
          </div>

          <input
            type="range"
            min={minSliderBound}
            max="99"
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="w-full h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />

          <div className="flex justify-between text-[10px] font-bold text-neutral-500 mt-3 uppercase tracking-wider">
            <span>High Recall (Loose)</span>
            <span>High Precision (Strict)</span>
          </div>
        </div>
      )}

      {totalAnomalies > 100 && (
        <div className="mb-4 flex items-center p-3 bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 text-xs rounded-lg">
          <AlertTriangle className="w-4 h-4 mr-2 shrink-0" />
          <span>
            Displaying the top 100 anomalies to maintain browser performance. All {totalAnomalies}{' '}
            will be handled during the Smart Cleaning step.
          </span>
        </div>
      )}

      <div className="bg-[#0A0A0A] border border-neutral-800 rounded-2xl overflow-hidden">
        {displayData.length > 0 ? (
          <div className="overflow-x-auto max-h-[600px] custom-scrollbar">
            <table className="w-full text-sm text-left table-fixed">
              <thead className="bg-neutral-900 text-neutral-500 sticky top-0 uppercase text-xs font-semibold z-10 shadow-sm">
                <tr>
                  <th className="px-6 py-4 w-[45%]">Row Data Snapshot</th>
                  <th className="px-6 py-4 w-[55%]">AI Explanations & SHAP Attribution</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800">
                {displayData.map((row, idx) => {
                  const originalIdx = data.indexOf(row);
                  const rowData: Record<string, unknown> = { ...row };
                  delete rowData.is_anomaly;
                  delete rowData.AI_Reason;
                  delete rowData.Threat_Score;
                  delete rowData.SHAP_Payload;

                  const shapData = parseShapPayload(row.SHAP_Payload);

                  return (
                    <motion.tr
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: idx * 0.02 }}
                      key={idx}
                      className="hover:bg-neutral-900/40"
                    >
                      <td className="px-6 py-5 w-[45%] align-top">
                        <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 pr-2">
                          {Object.entries(rowData).map(([key, val]) => (
                            <div
                              key={key}
                              className="flex flex-col bg-black/40 p-2.5 rounded-lg border border-neutral-800/60 min-w-0"
                            >
                              <span
                                className="text-[9px] text-neutral-500 uppercase font-bold tracking-wider mb-1 truncate"
                                title={key}
                              >
                                {key}
                              </span>
                              <span
                                className="text-xs font-mono text-neutral-200 truncate"
                                title={String(val)}
                              >
                                {typeof val === 'number' && !Number.isInteger(val)
                                  ? val.toFixed(4)
                                  : String(val ?? '—')}
                              </span>
                            </div>
                          ))}
                        </div>
                      </td>

                      <td className="px-6 py-5 w-[55%] align-top">
                        <div className="flex flex-col space-y-3">
                          <div className="flex items-start text-neutral-300 bg-purple-900/10 p-4 rounded-xl border border-purple-500/20 shadow-inner">
                            <div className="bg-purple-500/20 p-1.5 rounded-lg mr-3 mt-0.5 shrink-0">
                              <Activity className="w-4 h-4 text-purple-400" />
                            </div>
                            <span className="text-sm leading-relaxed font-medium">
                              {row.AI_Reason ||
                                'Flagged as an anomaly by the multi-dimensional detection model.'}
                            </span>
                          </div>

                          {row.Threat_Score !== undefined && row.Threat_Score > 0 && (
                            <div className="inline-flex items-center w-fit text-xs font-bold px-3 py-1.5 rounded-lg border border-red-900/50 bg-red-500/10 text-red-400">
                              <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />
                              Threat Score: {row.Threat_Score}%
                            </div>
                          )}

                          {shapData && shapData.length > 0 && (
                            <div className="bg-[#050505] border border-neutral-800/80 rounded-xl p-4">
                              <h5 className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-3 flex items-center">
                                Mathematical Attribution (SHAP)
                              </h5>
                              <div className="space-y-2.5">
                                {shapData.map((shap, sIdx) => {
                                  const isPositive = shap.impact > 0;
                                  const width = Math.min(
                                    Math.max(Math.abs(shap.impact) * 100, 5),
                                    100
                                  );
                                  return (
                                    <div
                                      key={sIdx}
                                      className="flex items-center justify-between group"
                                    >
                                      <span
                                        className="text-xs text-neutral-400 font-mono truncate w-1/3 pr-2"
                                        title={shap.feature}
                                      >
                                        {shap.feature}
                                      </span>
                                      <div className="w-1/2 bg-neutral-900 rounded-full h-1.5 overflow-hidden flex">
                                        <div
                                          className={`h-full rounded-full transition-all ${
                                            isPositive ? 'bg-red-500' : 'bg-emerald-500'
                                          }`}
                                          style={{ width: `${width}%` }}
                                        />
                                      </div>
                                      <span
                                        className={`text-[10px] font-mono w-12 text-right ${
                                          isPositive ? 'text-red-400' : 'text-emerald-400'
                                        }`}
                                      >
                                        {isPositive ? '+' : ''}
                                        {shap.impact.toFixed(2)}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          <div className="flex items-center space-x-2 pt-1">
                            <span className="text-[10px] uppercase font-bold text-neutral-600 mr-2">
                              Was this correct?
                            </span>
                            <button
                              onClick={() => submitFeedback(row, originalIdx, true)}
                              disabled={feedbackMap[originalIdx] !== undefined}
                              className={`flex items-center px-3 py-1.5 space-x-1.5 rounded-lg text-xs font-bold border transition-colors ${
                                feedbackMap[originalIdx] === 'correct'
                                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
                                  : feedbackMap[originalIdx] === 'incorrect'
                                  ? 'opacity-30 cursor-not-allowed bg-black text-neutral-600 border-neutral-800'
                                  : 'bg-[#0A0A0A] text-neutral-400 border-neutral-800 hover:text-emerald-400 hover:border-emerald-500/50'
                              }`}
                            >
                              <ThumbsUp className="w-3.5 h-3.5" />
                              <span>Yes</span>
                            </button>
                            <button
                              onClick={() => submitFeedback(row, originalIdx, false)}
                              disabled={feedbackMap[originalIdx] !== undefined}
                              className={`flex items-center px-3 py-1.5 space-x-1.5 rounded-lg text-xs font-bold border transition-colors ${
                                feedbackMap[originalIdx] === 'incorrect'
                                  ? 'bg-neutral-800/80 text-neutral-300 border-neutral-600'
                                  : feedbackMap[originalIdx] === 'correct'
                                  ? 'opacity-30 cursor-not-allowed bg-black text-neutral-600 border-neutral-800'
                                  : 'bg-[#0A0A0A] text-neutral-400 border-neutral-800 hover:text-neutral-300 hover:border-neutral-600'
                              }`}
                            >
                              <ThumbsDown className="w-3.5 h-3.5" />
                              <span>No</span>
                            </button>
                          </div>
                        </div>
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center flex flex-col items-center justify-center text-neutral-500">
            <CheckCircle className="w-12 h-12 mb-4 opacity-30" />
            <h3 className="text-lg font-medium text-neutral-400">
              No anomalies match this strictness
            </h3>
            <p className="text-sm mt-1">Lower the Threat Score threshold to view more rows.</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */
