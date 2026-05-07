"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Activity, Beaker, Watch, RefreshCw } from "lucide-react";
import api from "@/services/api.service";
import PlotWrapper from "@/components/PlotWrapper";

interface Props {
  sessionId: string;
  columns: string[];
}

export default function AdvancedIntelligence({ sessionId, columns }: Props) {
  const [activeTab, setActiveTab] = useState<"drift" | "synth" | "wearable">("drift");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // States for responses
  const [driftResult, setDriftResult] = useState<any>(null);
  const [synthResult, setSynthResult] = useState<any>(null);
  const [wearableResult, setWearableResult] = useState<any>(null);

  // Column Mapping
  const [invCol, setInvCol] = useState(columns.find(c => ["investigator", "inv_id"].some(k => c.toLowerCase().includes(k))) ?? "");
  const [timeCol, setTimeCol] = useState(columns.find(c => ["time", "date"].some(k => c.toLowerCase().includes(k))) ?? "");
  const [patientCol, setPatientCol] = useState(columns.find(c => ["patient", "subject"].some(k => c.toLowerCase().includes(k))) ?? "");
  const [metricCols, setMetricCols] = useState("");

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === "drift") {
        const res = await api.get(`/api/clinical/cohort-drift/${sessionId}`, {
          params: { investigator_col: invCol, time_col: timeCol, metric_cols: metricCols }
        });
        setDriftResult(res.data);
      } else if (activeTab === "synth") {
        const res = await api.get(`/api/clinical/synth-audit/${sessionId}`, {
          params: { investigator_col: invCol, metric_cols: metricCols }
        });
        setSynthResult(res.data);
      } else if (activeTab === "wearable") {
        const res = await api.get(`/api/clinical/wearable-gate/${sessionId}`, {
          params: { patient_col: patientCol, time_col: timeCol, telemetry_cols: metricCols }
        });
        setWearableResult(res.data);
      }
    } catch (e: any) {
      setError(e?.response?.data?.error ?? "Analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-black text-white mb-1">
          Advanced Intelligence <span className="text-purple-400">Layers</span>
        </h2>
        <p className="text-neutral-500 text-sm">
          Run deep statistical models: CohortDrift (F5), SynthAudit (F6), and WearableGate (F3).
        </p>
      </div>

      <div className="flex border-b border-white/10">
        <button onClick={() => setActiveTab("drift")} className={`pb-3 px-4 font-bold text-sm ${activeTab === "drift" ? "border-b-2 border-purple-500 text-purple-400" : "text-neutral-500"}`}>
          <Activity className="inline-block w-4 h-4 mr-2" /> CohortDrift
        </button>
        <button onClick={() => setActiveTab("synth")} className={`pb-3 px-4 font-bold text-sm ${activeTab === "synth" ? "border-b-2 border-purple-500 text-purple-400" : "text-neutral-500"}`}>
          <Beaker className="inline-block w-4 h-4 mr-2" /> SynthAudit
        </button>
        <button onClick={() => setActiveTab("wearable")} className={`pb-3 px-4 font-bold text-sm ${activeTab === "wearable" ? "border-b-2 border-purple-500 text-purple-400" : "text-neutral-500"}`}>
          <Watch className="inline-block w-4 h-4 mr-2" /> WearableGate
        </button>
      </div>

      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 flex flex-wrap gap-4 items-end">
        {activeTab !== "wearable" && (
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-neutral-500 mb-1.5 block">Investigator Col</label>
            <select value={invCol} onChange={e => setInvCol(e.target.value)} className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none">
              <option value="">— Select —</option>{columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}
        {activeTab === "wearable" && (
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-neutral-500 mb-1.5 block">Patient Col</label>
            <select value={patientCol} onChange={e => setPatientCol(e.target.value)} className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none">
              <option value="">— Select —</option>{columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}
        {activeTab !== "synth" && (
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-neutral-500 mb-1.5 block">Time Col</label>
            <select value={timeCol} onChange={e => setTimeCol(e.target.value)} className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none">
              <option value="">— Select —</option>{columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        )}
        <div className="flex-1 min-w-[160px]">
          <label className="text-xs text-neutral-500 mb-1.5 block">Metrics (comma-separated)</label>
          <input type="text" value={metricCols} onChange={e => setMetricCols(e.target.value)} className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none" />
        </div>

        <button onClick={runAnalysis} disabled={loading} className="px-6 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-bold rounded-xl disabled:opacity-40 hover:opacity-90 transition-opacity flex items-center gap-2">
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />} Run Layer
        </button>
      </div>

      {error && <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">{error}</div>}

      {/* Basic output rendering */}
      <AnimatePresence>
        {activeTab === "drift" && driftResult && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5 bg-white/[0.02] border border-white/5 rounded-2xl">
            <h3 className="font-bold text-white mb-4 flex items-center gap-2"><Activity className="text-purple-400" /> Cohort Drift Flags: {driftResult.flagged_investigators}</h3>
            <div className="space-y-4">
              {Object.entries(driftResult.drift_reports || {}).map(([inv, report]: [string, any]) => (
                <div key={inv} className="p-4 border border-white/10 rounded-xl bg-black/20">
                  <h4 className="text-sm font-bold text-white mb-2">Investigator: {inv} <span className="text-rose-400 ml-2">(PDS: {report.phase_drift_score})</span></h4>

                  {report.phase_plot_json && (
                    <div className="mt-4 rounded-xl overflow-hidden mb-4">
                      <PlotWrapper
                        data={report.phase_plot_json.data}
                        layout={{ ...report.phase_plot_json.layout, height: 350 }}
                        style={{ height: 350 }}
                      />
                    </div>
                  )}

                  {report.flagged_metrics && report.flagged_metrics.length > 0 && (
                    <div>
                      <p className="text-xs text-neutral-500 mb-1 uppercase tracking-widest">Flagged Metrics</p>
                      <pre className="text-xs text-neutral-400 overflow-auto bg-neutral-900 p-2 rounded-lg border border-white/5">
                        {JSON.stringify(report.flagged_metrics, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
        {activeTab === "synth" && synthResult && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            <div className="p-5 bg-white/[0.02] border border-white/5 rounded-2xl">
              <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                <Beaker className="text-purple-400" size={16} />
                Synthetic Deviation Analysis
                <span className="ml-2 text-xs bg-white/5 border border-white/10 rounded-lg px-2 py-0.5 text-neutral-400">
                  {synthResult.flagged_investigators} flagged
                </span>
              </h3>
              <div className="space-y-4">
                {Object.entries(synthResult.synth_audit_reports || {}).map(([inv, report]: [string, any]) => {
                  const sds = report?.synthetic_deviation_score ?? 0;
                  const sdsColor = sds > 60 ? "text-red-400" : sds > 30 ? "text-amber-400" : "text-emerald-400";
                  const sdsBg = sds > 60 ? "bg-red-500/10 border-red-500/30" : sds > 30 ? "bg-amber-500/10 border-amber-500/30" : "bg-emerald-500/10 border-emerald-500/30";
                  return (
                    <div key={inv} className={`p-4 rounded-xl border ${sdsBg}`}>
                      <div className="flex items-center gap-4 mb-3">
                        <div className="text-center">
                          <p className={`text-3xl font-black font-mono ${sdsColor}`}>{sds.toFixed(1)}</p>
                          <p className="text-[9px] text-neutral-500 uppercase tracking-wider">SDS Score</p>
                        </div>
                        <div>
                          <p className="font-bold text-white">{inv}</p>
                          {report?.narrative && (
                            <p className="text-xs text-neutral-300 italic mt-0.5 leading-relaxed">{report.narrative}</p>
                          )}
                        </div>
                      </div>
                      {report?.deviations && report.deviations.length > 0 && (
                        <div className="space-y-1.5 mt-3 pt-3 border-t border-white/5">
                          <p className="text-[10px] text-neutral-600 uppercase tracking-wider mb-2">Per-Metric Deviations</p>
                          {report.deviations.map((d: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              <span className="text-neutral-500 w-32 truncate">{d.metric}</span>
                              <div className="flex-1 bg-white/5 rounded-full h-1.5">
                                <div
                                  className="h-full rounded-full bg-rose-500"
                                  style={{ width: `${Math.min(d.ks_statistic * 100 * 3, 100)}%` }}
                                />
                              </div>
                              <span className="text-neutral-400 font-mono w-10 text-right">{(d.ks_statistic ?? 0).toFixed(3)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
                {Object.keys(synthResult.synth_audit_reports || {}).length === 0 && (
                  <p className="text-neutral-500 text-sm text-center py-6">No investigators returned. Try different metric columns.</p>
                )}
              </div>
            </div>
          </motion.div>
        )}
        {activeTab === "wearable" && wearableResult && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            <div className="p-5 bg-white/[0.02] border border-white/5 rounded-2xl">
              <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                <Watch className="text-purple-400" size={16} />
                Wearable Authentication
                <span className="ml-2 text-xs bg-white/5 border border-white/10 rounded-lg px-2 py-0.5 text-neutral-400">
                  {wearableResult.flagged_patients} flagged
                </span>
              </h3>
              <div className="space-y-3">
                {Object.entries(wearableResult.wearable_reports || {}).map(([patient, report]: [string, any]) => {
                  const sas = report?.sas_score ?? 0;
                  const sasColor = sas < 40 ? "text-red-400" : sas < 70 ? "text-amber-400" : "text-emerald-400";
                  const sasBg = sas < 40 ? "bg-red-500/10 border-red-500/30" : sas < 70 ? "bg-amber-500/10 border-amber-500/30" : "bg-emerald-500/10 border-emerald-500/30";
                  return (
                    <div key={patient} className={`p-4 rounded-xl border ${sasBg}`}>
                      <div className="flex items-center gap-4">
                        <div className="text-center">
                          <p className={`text-2xl font-black font-mono ${sasColor}`}>{sas.toFixed(1)}</p>
                          <p className="text-[9px] text-neutral-500 uppercase">SAS</p>
                        </div>
                        <div>
                          <p className="font-bold text-white text-sm">{patient}</p>
                          {report?.flags && report.flags.map((f: string, i: number) => (
                            <p key={i} className="text-xs text-amber-300 mt-0.5">⚠ {f}</p>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
                {Object.keys(wearableResult.wearable_reports || {}).length === 0 && (
                  <p className="text-neutral-500 text-sm text-center py-6">No flagged patients. Data appears authentic.</p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}