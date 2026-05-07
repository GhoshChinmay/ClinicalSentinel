"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity, Clock, AlertTriangle, User, RefreshCw,
  ChevronDown, ChevronUp, TrendingUp
} from "lucide-react";
import api from "@/services/api.service";

interface BAEEvent {
  type: string;
  description: string;
  severity: "high" | "medium" | "low";
  timestamp?: string;
  value?: number;
}

interface BehaviorReport {
  investigator_id: string;
  bae_count: number;
  events: BAEEvent[];
  entry_hours: Record<string, number>;
  daily_volumes: Record<string, number>;
  typing_intervals?: number[];
}

interface Props {
  sessionId: string;
  columns: string[];
}

const SEVERITY_STYLES = {
  high:   "bg-red-500/10 border-red-500/30 text-red-300",
  medium: "bg-amber-500/10 border-amber-500/30 text-amber-300",
  low:    "bg-blue-500/10 border-blue-500/30 text-blue-300",
};

function HourHeatmap({ hourData }: { hourData: Record<string, number> }) {
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const maxVal = Math.max(...Object.values(hourData), 1);

  const getColor = (hour: number) => {
    const val = hourData[String(hour)] ?? 0;
    const intensity = val / maxVal;
    const isNight = hour < 6 || hour >= 22;
    if (val === 0) return "bg-white/5";
    if (isNight && intensity > 0.2) return "bg-red-500";
    if (intensity > 0.7) return "bg-purple-500";
    if (intensity > 0.4) return "bg-purple-400/60";
    return "bg-purple-300/30";
  };

  return (
    <div className="space-y-2">
      <p className="text-xs text-neutral-500 uppercase tracking-widest">Entry Density by Hour (24h)</p>
      <div className="flex gap-1 items-end h-14">
        {hours.map(h => {
          const val = hourData[String(h)] ?? 0;
          const height = Math.max((val / maxVal) * 100, 4);
          const isNight = h < 6 || h >= 22;
          return (
            <div key={h} className="flex-1 flex flex-col items-center gap-1 group relative">
              <div
                className={`w-full rounded-t-sm transition-all duration-500 ${getColor(h)} ${isNight && val > 0 ? "ring-1 ring-red-500/50" : ""}`}
                style={{ height: `${height}%` }}
                title={`${h}:00 — ${val} entries`}
              />
              {val > 0 && (
                <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-neutral-800 text-white text-xs px-1.5 py-0.5 rounded hidden group-hover:block whitespace-nowrap z-10">
                  {h}:00 — {val}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-neutral-600">
        <span>00:00</span>
        <span className="text-red-500 text-xs">Night Risk Window</span>
        <span>23:00</span>
      </div>
    </div>
  );
}

function DailyVolumeChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort(([a], [b]) => a.localeCompare(b)).slice(-30);
  if (entries.length === 0) return null;
  const maxVal = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="space-y-2">
      <p className="text-xs text-neutral-500 uppercase tracking-widest">Daily Entry Volume (last 30 days)</p>
      <div className="flex gap-0.5 items-end h-12">
        {entries.map(([date, count]) => {
          const h = (count / maxVal) * 100;
          const isBurst = count > maxVal * 0.7;
          return (
            <div key={date} className="flex-1 group relative" title={`${date}: ${count}`}>
              <div
                className={`w-full rounded-t-sm ${isBurst ? "bg-red-400" : "bg-purple-500/40"}`}
                style={{ height: `${Math.max(h, 3)}%` }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProfileCard({ report }: { report: BehaviorReport }) {
  const [open, setOpen] = useState(false);
  const hasHighBae = report.events.some(e => e.severity === "high");

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`border rounded-2xl overflow-hidden transition-all ${
        hasHighBae
          ? "bg-red-500/5 border-red-500/30"
          : report.bae_count > 0
          ? "bg-amber-500/5 border-amber-500/20"
          : "bg-white/[0.02] border-white/5"
      }`}
    >
      <div
        className="flex items-center gap-4 p-5 cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center shrink-0">
          <User size={20} className={hasHighBae ? "text-red-400" : "text-neutral-400"} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-white">{report.investigator_id}</h3>
            {report.bae_count > 0 && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                hasHighBae ? "bg-red-500/20 text-red-300" : "bg-amber-500/20 text-amber-300"
              }`}>
                {report.bae_count} BAE{report.bae_count !== 1 ? "s" : ""}
              </span>
            )}
            {report.bae_count === 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">
                ✓ No anomalies
              </span>
            )}
          </div>
          <p className="text-neutral-500 text-xs mt-1">
            Behavioral Anomaly Events: {report.bae_count}
          </p>
        </div>
        <button className="text-neutral-600 hover:text-white transition-colors">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-white/5"
          >
            <div className="p-5 space-y-5">
              {Object.keys(report.entry_hours ?? {}).length > 0 && (
                <HourHeatmap hourData={report.entry_hours} />
              )}
              {Object.keys(report.daily_volumes ?? {}).length > 0 && (
                <DailyVolumeChart data={report.daily_volumes} />
              )}
              {report.events.length > 0 && (
                <div>
                  <p className="text-xs text-neutral-500 uppercase tracking-widest mb-3">
                    Behavioral Anomaly Events
                  </p>
                  <div className="space-y-2">
                    {report.events.map((ev, i) => (
                      <div
                        key={i}
                        className={`border rounded-xl p-3 text-xs flex items-start gap-2 ${
                          SEVERITY_STYLES[ev.severity] ?? SEVERITY_STYLES.low
                        }`}
                      >
                        <AlertTriangle size={12} className="shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold uppercase tracking-wide mr-2">{ev.type}</span>
                          {ev.description}
                          {ev.timestamp && (
                            <span className="ml-2 text-neutral-500">@ {ev.timestamp}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function InvestiProfile({ sessionId, columns }: Props) {
  const [reports, setReports] = useState<Record<string, BehaviorReport>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invCol, setInvCol] = useState(
    columns.find(c => ["investigator","doctor","inv_id"].some(k => c.toLowerCase().includes(k))) ?? ""
  );
  const [timeCol, setTimeCol] = useState(
    columns.find(c => ["timestamp","time","date","entry"].some(k => c.toLowerCase().includes(k))) ?? ""
  );

  const run = async () => {
    if (!invCol || !timeCol) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/clinical/investi-profile/${sessionId}`, {
        params: { investigator_col: invCol, time_col: timeCol },
      });
      setReports(res.data.behavioral_reports ?? {});
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err?.response?.data?.error ?? "InvestiProfile failed.");
    } finally {
      setLoading(false);
    }
  };

  const reportList = Object.values(reports).sort((a, b) => b.bae_count - a.bae_count);
  const flaggedCount = reportList.filter(r => r.bae_count > 0).length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-black text-white mb-1">
          InvestiProfile <span className="text-purple-400">F7</span>
        </h2>
        <p className="text-neutral-500 text-sm">
          Longitudinal behavioral fingerprinting — detects night-hour data dumps, speed-typing, and sudden behavioral shifts
        </p>
      </div>

      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[160px]">
          <label className="text-xs text-neutral-500 mb-1.5 block flex items-center gap-1">
            <User size={10} /> Investigator Column
          </label>
          <select
            value={invCol}
            onChange={e => setInvCol(e.target.value)}
            className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50"
          >
            <option value="">— Select —</option>
            {columns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="text-xs text-neutral-500 mb-1.5 block flex items-center gap-1">
            <Clock size={10} /> Timestamp Column
          </label>
          <select
            value={timeCol}
            onChange={e => setTimeCol(e.target.value)}
            className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500/50"
          >
            <option value="">— Select —</option>
            {columns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <button
          onClick={run}
          disabled={!invCol || !timeCol || loading}
          className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-bold rounded-xl disabled:opacity-40 hover:opacity-90 transition-opacity text-sm"
        >
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
          {loading ? "Profiling…" : "Profile Investigators"}
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">{error}</div>
      )}

      {reportList.length > 0 && (
        <>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Total Investigators", val: reportList.length, color: "text-white", icon: <User size={14}/> },
              { label: "With BAE Flags", val: flaggedCount, color: "text-amber-400", icon: <AlertTriangle size={14}/> },
              { label: "Critical (High BAE)", val: reportList.filter(r => r.events.some(e => e.severity === "high")).length, color: "text-red-400", icon: <TrendingUp size={14}/> },
            ].map(({ label, val, color, icon }) => (
              <div key={label} className="bg-white/[0.02] border border-white/5 rounded-xl p-4 text-center">
                <div className="flex items-center justify-center gap-1 text-xs text-neutral-500 mb-1">{icon} {label}</div>
                <p className={`font-black text-2xl font-mono ${color}`}>{val}</p>
              </div>
            ))}
          </div>
          <div className="space-y-3">
            {reportList.map(r => <ProfileCard key={r.investigator_id} report={r} />)}
          </div>
        </>
      )}

      {!reportList.length && !loading && (
        <div className="flex flex-col items-center py-20 text-center">
          <div className="w-16 h-16 bg-purple-500/10 rounded-2xl flex items-center justify-center mb-4">
            <Activity className="w-8 h-8 text-purple-400" />
          </div>
          <h3 className="text-lg font-bold text-white mb-2">Behavioral Fingerprinter Ready</h3>
          <p className="text-neutral-500 text-sm max-w-xs">
            Select the investigator and timestamp columns, then run the profiler to detect night-hour data dumps and behavioral shifts.
          </p>
        </div>
      )}
    </div>
  );
}
