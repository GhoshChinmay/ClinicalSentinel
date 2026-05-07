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
  ArrowRight,
  Radar,
  GitBranch,
  Wand2,
} from 'lucide-react';
import { useDetection } from '@/hooks/use-detection';
import BenfordChart from './BenfordChart';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export interface DetectionProps {
  sessionId: string;
}

interface DriftedFeature {
  feature: string;
  ks_stat: number;
  p_value: number;
}

interface DriftReport {
  drifted_features: DriftedFeature[];
  baseline_present: boolean;
}

/* ─── Helpers ────────────────────────────────────────────────────────────────────────────── */

const parseShapPayload = (payload?: string): Array<{ feature: string; impact: number }> | null => {
  if (!payload || payload === '[]') return null;
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
};

const parseCounterfactualPayload = (
  payload?: string
): Record<string, { from: number; to: number }> | null => {
  if (!payload || payload === '{}' || payload === '[]') return null;
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
};

// Internal columns produced by the backend that should never appear in the raw data grid
const INTERNAL_COLS = new Set([
  'is_anomaly',
  'AI_Reason',
  'Threat_Score',
  'SHAP_Payload',
  'Counterfactual_Payload',
  'lof_score',
  'lstm_anomaly_score',
  'ecod_score',
]);

/* ─── Component ──────────────────────────────────────────────────────────────────────────── */

/**
 * Detection component to display identified anomalies, SHAP attributions,
 * DiCE counterfactuals, LOF scores, and KS drift warnings.
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
    driftReport,
    recommendation,
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

  const drift = driftReport as DriftReport | undefined;
  const hasDrift = drift && drift.drifted_features && drift.drifted_features.length > 0;

  return (
    <div className="w-full mt-6">

      {/* ── Scan Summary Header ───────────────────────────────────────────────── */}
      <div className="flex items-center justify-between bg-neutral-900 border border-neutral-800 p-6 rounded-2xl mb-4">
        <div>
          <h3 className="text-xl font-semibold flex items-center">
            <ShieldAlert className="w-5 h-5 text-red-400 mr-2" /> Scan Complete
          </h3>
          <p className="text-sm text-neutral-400">
            Our Multi-Modal AI scanned numbers, text, and categories for errors.
          </p>
          {recommendation && (
            <p className="text-[11px] text-neutral-600 mt-1 font-mono">
              Engine: {recommendation}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-red-400">{totalAnomalies}</p>
          <p className="text-xs text-neutral-500 uppercase font-bold tracking-wider">
            Anomalies Found
          </p>
        </div>
      </div>

      {/* ── KS Drift Warning Banner ───────────────────────────────────────────── */}
      {hasDrift && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 p-4 bg-orange-500/10 border border-orange-500/25 rounded-2xl"
        >
          <div className="flex items-center mb-2">
            <GitBranch className="w-4 h-4 text-orange-400 mr-2 shrink-0" />
            <span className="text-xs font-bold text-orange-400 uppercase tracking-wider">
              Feature Drift Detected — Threshold Recalibration Recommended
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 mt-2">
            {drift!.drifted_features.map((f) => (
              <div
                key={f.feature}
                className="flex items-center justify-between bg-orange-500/5 border border-orange-500/15 rounded-lg px-3 py-1.5"
              >
                <span className="text-xs text-orange-300 font-mono truncate pr-2">{f.feature}</span>
                <span className="text-[10px] text-neutral-500 font-mono shrink-0">
                  KS {f.ks_stat} · p={f.p_value}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-neutral-500 mt-2">
            These features have shifted significantly from the training baseline. Consider re-running
            with fresh data or triggering a retraining job.
          </p>
        </motion.div>
      )}

      {/* ── Benford's Law Chart ───────────────────────────────────────────────── */}
      {data.length > 0 && <BenfordChart data={data} />}

      {/* ── Threat Score Slider ───────────────────────────────────────────────── */}
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

      {/* ── Performance Warning ───────────────────────────────────────────────── */}
      {totalAnomalies > 100 && (
        <div className="mb-4 flex items-center p-3 bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 text-xs rounded-lg">
          <AlertTriangle className="w-4 h-4 mr-2 shrink-0" />
          <span>
            Displaying the top 100 anomalies to maintain browser performance. All {totalAnomalies}{' '}
            will be handled during the Smart Cleaning step.
          </span>
        </div>
      )}

      {/* ── Anomaly Table ─────────────────────────────────────────────────────── */}
      <div className="bg-[#0A0A0A] border border-neutral-800 rounded-2xl overflow-hidden">
        {displayData.length > 0 ? (
          <div className="overflow-x-auto max-h-[600px] custom-scrollbar" data-lenis-prevent>
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

                  const shapData = parseShapPayload(row.SHAP_Payload as string);
                  const cfData = parseCounterfactualPayload(row.Counterfactual_Payload as string);

                  // ── BUILD THE RAW SNAPSHOT ──
                  const rowData: Record<string, unknown> = {};

                  for (const [key, val] of Object.entries(row)) {
                    const lowerKey = key.toLowerCase();

                    // Check if it's an AI-generated/internal column
                    const isEngineered =
                      INTERNAL_COLS.has(key) ||
                      lowerKey.endsWith('_freq') ||
                      lowerKey.endsWith('_length') ||
                      lowerKey.endsWith('_ratio') ||
                      lowerKey.startsWith('nlp_pc') ||
                      lowerKey.startsWith('velocity_') ||
                      lowerKey.includes('_entity_z');

                    if (!isEngineered) {
                      // Show all original dataset columns
                      rowData[key] = val;
                    }
                  }

                  // LOF score — only show if meaningfully elevated (> 1.0 after inversion)
                  const lofScore =
                    typeof row.lof_score === 'number' && row.lof_score > 1.0
                      ? row.lof_score
                      : null;

                  return (
                    <motion.tr
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: idx * 0.02 }}
                      key={idx}
                      className="hover:bg-neutral-900/40"
                    >
                      {/* ── Left: Raw data grid ─────────────────────────────── */}
                      <td className="px-6 py-5 w-[45%] align-top border-r border-neutral-800/50">
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

                      {/* ── Right: Explanations ─────────────────────────────── */}
                      <td className="px-6 py-5 w-[55%] align-top">
                        <div className="flex flex-col space-y-3">

                          {/* AI Narrative */}
                          <div className="flex items-start text-neutral-300 bg-purple-900/10 p-4 rounded-xl border border-purple-500/20 shadow-inner">
                            <div className="bg-purple-500/20 p-1.5 rounded-lg mr-3 mt-0.5 shrink-0">
                              <Activity className="w-4 h-4 text-purple-400" />
                            </div>
                            <span className="text-sm leading-relaxed font-medium">
                              {row.AI_Reason ||
                                'Flagged as an anomaly by the multi-dimensional detection model.'}
                            </span>
                          </div>

                          {/* Score badges row */}
                          <div className="flex flex-wrap gap-2">
                            {row.Threat_Score !== undefined && (row.Threat_Score as number) > 0 && (
                              <div className="inline-flex items-center text-xs font-bold px-3 py-1.5 rounded-lg border border-red-900/50 bg-red-500/10 text-red-400">
                                <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />
                                Threat Score: {row.Threat_Score as number}%
                              </div>
                            )}

                            {/* LOF badge — only shown when LOF was the detection driver */}
                            {lofScore !== null && (
                              <div className="inline-flex items-center text-xs font-bold px-3 py-1.5 rounded-lg border border-blue-900/50 bg-blue-500/10 text-blue-400">
                                <Radar className="w-3.5 h-3.5 mr-1.5" />
                                LOF: {(lofScore as number).toFixed(3)}
                              </div>
                            )}
                          </div>

                          {/* SHAP Attribution */}
                          {shapData && shapData.length > 0 && (
                            <div className="bg-[#050505] border border-neutral-800/80 rounded-xl p-4">
                              <h5 className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-3">
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
                                          className={`h-full rounded-full transition-all ${isPositive ? 'bg-red-500' : 'bg-emerald-500'
                                            }`}
                                          style={{ width: `${width}%` }}
                                        />
                                      </div>
                                      <span
                                        className={`text-[10px] font-mono w-12 text-right ${isPositive ? 'text-red-400' : 'text-emerald-400'
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

                          {/* ── DiCE Counterfactual Explanations UI ── */}
                          {cfData && Object.keys(cfData).length > 0 && (
                            <div className="bg-[#050505] border border-blue-900/40 rounded-xl p-4 relative overflow-hidden mt-3">
                              <div className="absolute left-0 top-0 w-1 h-full bg-blue-500/50 rounded-l-xl" />
                              <h5 className="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-3 flex items-center">
                                <Wand2 className="w-3.5 h-3.5 mr-1.5" /> How to Fix This (Counterfactual AI)
                              </h5>
                              <div className="space-y-2">
                                {Object.entries(cfData).map(([feat, changes]) => (
                                  <div key={feat} className="flex items-center justify-between text-xs">
                                    <span
                                      className="text-neutral-400 font-mono truncate w-1/3 pr-2"
                                      title={feat}
                                    >
                                      {feat}
                                    </span>
                                    <div className="flex items-center space-x-3 w-2/3 justify-end font-mono">
                                      <span className="text-red-400 bg-red-500/10 px-2 py-0.5 rounded line-through decoration-red-500/50">
                                        {changes.from}
                                      </span>
                                      <ArrowRight className="w-3 h-3 text-neutral-600 shrink-0" />
                                      <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-bold">
                                        {changes.to}
                                      </span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                              <p className="text-[10px] text-neutral-600 mt-3 italic">
                                If these values were different, this row would not have been flagged.
                              </p>
                            </div>
                          )}

                          {/* Analyst Feedback */}
                          <div className="flex items-center space-x-2 pt-1 border-t border-neutral-800/50 mt-4">
                            <span className="text-[10px] uppercase font-bold text-neutral-600 mr-2 mt-2">
                              Was this correct?
                            </span>
                            <button
                              onClick={() => submitFeedback(row, originalIdx, true)}
                              disabled={feedbackMap[originalIdx] !== undefined}
                              className={`flex items-center px-3 py-1.5 mt-2 space-x-1.5 rounded-lg text-xs font-bold border transition-colors ${feedbackMap[originalIdx] === 'correct'
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
                              className={`flex items-center px-3 py-1.5 mt-2 space-x-1.5 rounded-lg text-xs font-bold border transition-colors ${feedbackMap[originalIdx] === 'incorrect'
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