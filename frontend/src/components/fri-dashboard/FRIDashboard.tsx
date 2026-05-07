"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle, Shield, Activity, ChevronDown, ChevronUp,
  FlaskConical, Clock, BarChart2, Microscope, RefreshCw,
  Settings2, FileText, Brain, Network, Scale, Watch
} from "lucide-react";
import api from "@/services/api.service";
import { API_BASE } from "@/constants/config";

// ── Sub-panel components (already built) ─────────────────────────────────────
import InvestiProfile from "@/components/investi-profile/InvestiProfile";
import CollusionNetwork from "@/components/collusion-network/CollusionNetwork";
import RegRagCompliance from "@/components/regrag-compliance/RegRagCompliance";
import AdvancedIntelligence from "@/components/advanced-intelligence/AdvancedIntelligence";

// ── Types ─────────────────────────────────────────────────────────────────────

interface LayerBreakdown {
  L1_benfords_law: number;
  L2_temporal_burst: number;
  L3_statistical_outlier: number;
  L4_round_number: number;
  L5_last_digit_entropy: number;
  L6_clinical_plausibility: number;
  L7_behavioral_profile: number;
}

interface BAEEvent {
  type: string;        // "NIGHT_SHIFT" | "SPEED_TYPING" | "VOLUME_SPIKE" | "WEEKEND_WARRIOR"
  description: string;
  severity: "high" | "medium" | "low";
}

interface InvestigatorFRI {
  investigator_id: string;
  fri_score: number;
  risk_band: "high" | "review" | "low";
  risk_label: string;
  entry_count: number;
  layer_breakdown: LayerBreakdown;
  bae_events: BAEEvent[];
  pds_score: number;
  sds_score: number;
  crcs_score: number;
  note?: string;
  narrative?: string;
}

interface FRISummary {
  total_investigators: number;
  high_risk_count: number;
  needs_review_count: number;
  low_risk_count: number;
  highest_fri: number;
  mean_fri: number;
}

interface FRIResult {
  investigators: Record<string, InvestigatorFRI>;
  summary: FRISummary;
}

interface Props {
  sessionId: string;
  columns: string[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const LAYER_COLORS: Record<string, string> = {
  L1_benfords_law: "#f43f5e",
  L2_temporal_burst: "#fb923c",
  L3_statistical_outlier: "#a78bfa",
  L4_round_number: "#fbbf24",
  L5_last_digit_entropy: "#34d399",
  L6_clinical_plausibility: "#38bdf8",
  L7_behavioral_profile: "#e879f9",
};

const LAYER_LABELS: Record<string, string> = {
  L1_benfords_law: "L1 Benford's Law",
  L2_temporal_burst: "L2 Temporal Burst",
  L3_statistical_outlier: "L3 Statistical",
  L4_round_number: "L4 Round Number",
  L5_last_digit_entropy: "L5 Digit Entropy",
  L6_clinical_plausibility: "L6 Plausibility",
  L7_behavioral_profile: "L7 Behavioral",
};

const RISK_CONFIG = {
  high:   { bg: "bg-red-500/10",     border: "border-red-500/40",     text: "text-red-400",     badge: "bg-red-500/20 text-red-300",     glow: "shadow-[0_0_30px_rgba(239,68,68,0.15)]" },
  review: { bg: "bg-amber-500/10",   border: "border-amber-500/40",   text: "text-amber-400",   badge: "bg-amber-500/20 text-amber-300", glow: "shadow-[0_0_30px_rgba(245,158,11,0.12)]" },
  low:    { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400", badge: "bg-emerald-500/20 text-emerald-300", glow: "" },
};

// ── FRI Sub-components ────────────────────────────────────────────────────────

function ScoreRing({ score, band }: { score: number; band: string }) {
  const r = 40;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = band === "high" ? "#ef4444" : band === "review" ? "#f59e0b" : "#10b981";
  return (
    <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
      <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} stroke="#ffffff08" strokeWidth="7" fill="none" />
        <motion.circle
          cx="48" cy="48" r={r}
          stroke={color}
          strokeWidth="7" fill="none"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
          strokeLinecap="round"
        />
      </svg>
      <motion.span
        className="font-black text-2xl font-mono"
        style={{ color }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        {score}
      </motion.span>
    </div>
  );
}

function LayerBar({ label, value, color }: { label: string; value: number; color: string }) {
  if (value === 0) return null;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-neutral-500 w-28 shrink-0 truncate">{label}</span>
      <div className="flex-1 bg-white/5 rounded-full h-1.5 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span className="text-neutral-400 w-8 text-right font-mono">{value}</span>
    </div>
  );
}

function InvestigatorCard({ data }: { data: InvestigatorFRI }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = RISK_CONFIG[data.risk_band] ?? RISK_CONFIG.low;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${cfg.bg} ${cfg.border} ${cfg.glow} border rounded-2xl p-5 transition-all duration-300`}
    >
      <div className="flex items-center gap-4">
        <ScoreRing score={data.fri_score} band={data.risk_band} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h3 className="font-bold text-white text-base truncate">{data.investigator_id}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg.badge}`}>
              {data.risk_label}
            </span>
            {data.note && (
              <span className="text-xs text-neutral-600 italic">{data.note}</span>
            )}
          </div>
          <p className="text-neutral-500 text-xs mb-3">{data.entry_count} records analysed</p>
          <div className="space-y-1.5">
            {Object.entries(data.layer_breakdown)
              .filter(([, v]) => v > 0)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 3)
              .map(([k, v]) => (
                <LayerBar key={k} label={LAYER_LABELS[k] ?? k} value={v} color={LAYER_COLORS[k] ?? "#6366f1"} />
              ))}
          </div>
          {data.narrative && (
            <div className="mt-3 p-3 bg-purple-500/5 border border-purple-500/20 rounded-xl">
              <p className="text-xs text-purple-200 italic flex items-start gap-2 leading-relaxed">
                <Brain className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
                <span>{data.narrative}</span>
              </p>
            </div>
          )}
        </div>
        {data.fri_score > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="shrink-0 p-2 rounded-xl hover:bg-white/5 text-neutral-500 hover:text-white transition-colors"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        )}
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-4 pt-4 border-t border-white/5 space-y-4">
              <div>
                <p className="text-xs text-neutral-500 uppercase tracking-widest mb-2">All 7 Forensic Layers</p>
                <div className="space-y-1.5">
                  {Object.entries(data.layer_breakdown).map(([k, v]) => (
                    <LayerBar key={k} label={LAYER_LABELS[k] ?? k} value={v} color={LAYER_COLORS[k] ?? "#6366f1"} />
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Phase Drift",    value: data.pds_score,  unit: "PDS" },
                  { label: "Synth Deviation", value: data.sds_score, unit: "SDS" },
                  { label: "Collusion Risk", value: data.crcs_score, unit: "CRCS" },
                ].map(({ label, value, unit }) => (
                  <div key={unit} className="bg-white/5 rounded-xl p-3 text-center">
                    <p className="text-xs text-neutral-500 mb-1">{label}</p>
                    <p className="font-black text-lg text-white font-mono">{value.toFixed(1)}</p>
                    <p className="text-xs text-neutral-600">{unit}</p>
                  </div>
                ))}
              </div>
              {data.bae_events.length > 0 && (
                <div>
                  <p className="text-xs text-neutral-500 uppercase tracking-widest mb-2">Behavioral Anomaly Events</p>
                  {data.bae_events.map((ev, i) => {
                    // Handle both structured objects and legacy plain strings
                    if (typeof ev === "string") {
                      return (
                        <div key={i} className="flex items-start gap-2 text-xs text-amber-300 mb-1">
                          <AlertTriangle size={12} className="shrink-0 mt-0.5" />
                          <span>{ev}</span>
                        </div>
                      );
                    }
                    const sevColor = ev.severity === "high" ? "text-red-300 bg-red-500/10 border-red-500/20"
                      : ev.severity === "medium" ? "text-amber-300 bg-amber-500/10 border-amber-500/20"
                      : "text-blue-300 bg-blue-500/10 border-blue-500/20";
                    const typeLabel = ev.type.replace(/_/g, " ");
                    return (
                      <div key={i} className={`flex items-start gap-2 text-xs mb-2 p-2 rounded-lg border ${sevColor}`}>
                        <AlertTriangle size={12} className="shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <span className="font-bold uppercase tracking-wide mr-2">{typeLabel}</span>
                          <span className="opacity-80">{ev.description}</span>
                        </div>
                        <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border opacity-70">
                          {ev.severity}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Column Mapper ─────────────────────────────────────────────────────────────

function ColumnMapper({
  columns,
  onRun,
  loading,
}: {
  columns: string[];
  onRun: (cfg: { investigator_col: string; time_col: string; metric_cols: string[]; shared_attr_cols: string[] }) => void;
  loading: boolean;
}) {
  const guess = (kws: string[]) => columns.find(c => kws.some(k => c.toLowerCase().includes(k))) ?? "";

  const [investigatorCol, setInvestigatorCol] = useState(
    guess(["investigator", "doctor", "physician", "inv_id", "site_inv"])
  );
  const [timeCol, setTimeCol] = useState(
    guess(["timestamp", "time", "date", "entry"])
  );
  const [metricColsRaw, setMetricColsRaw] = useState(
    columns.filter(c => {
      const lc = c.toLowerCase();
      return ["bp", "pressure", "rate", "weight", "glucose", "creatinine", "bmi", "age", "temp"].some(k => lc.includes(k));
    }).join(",")
  );
  const [sharedColsRaw, setSharedColsRaw] = useState(
    guess(["site", "cro", "sponsor", "hospital"])
  );

  const sel = (val: string, set: (v: string) => void) => (
    <select
      value={val}
      onChange={e => set(e.target.value)}
      className="bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white w-full focus:outline-none focus:border-purple-500/50"
    >
      <option value="">— Select column —</option>
      {columns.map(c => <option key={c} value={c}>{c}</option>)}
    </select>
  );

  return (
    <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Settings2 size={16} className="text-purple-400" />
        <h3 className="font-semibold text-white text-sm">Column Mapping</h3>
        <span className="text-xs text-neutral-500">— Map dataset columns to forensic roles</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs text-neutral-500 mb-1.5 block">Investigator / Doctor ID *</label>
          {sel(investigatorCol, setInvestigatorCol)}
        </div>
        <div>
          <label className="text-xs text-neutral-500 mb-1.5 block">Entry Timestamp *</label>
          {sel(timeCol, setTimeCol)}
        </div>
        <div>
          <label className="text-xs text-neutral-500 mb-1.5 block">Clinical Metric Columns (comma-separated)</label>
          <input
            type="text"
            value={metricColsRaw}
            onChange={e => setMetricColsRaw(e.target.value)}
            placeholder="systolic_bp,diastolic_bp,heart_rate..."
            className="bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white w-full focus:outline-none focus:border-purple-500/50"
          />
        </div>
        <div>
          <label className="text-xs text-neutral-500 mb-1.5 block">Shared Attribute Columns (site, CRO…)</label>
          <input
            type="text"
            value={sharedColsRaw}
            onChange={e => setSharedColsRaw(e.target.value)}
            placeholder="site_id,cro_name..."
            className="bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white w-full focus:outline-none focus:border-purple-500/50"
          />
        </div>
      </div>
      <button
        onClick={() =>
          onRun({
            investigator_col: investigatorCol,
            time_col: timeCol,
            metric_cols: metricColsRaw.split(",").map(s => s.trim()).filter(Boolean),
            shared_attr_cols: sharedColsRaw.split(",").map(s => s.trim()).filter(Boolean),
          })
        }
        disabled={!investigatorCol || loading}
        className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-rose-600 text-white font-bold rounded-xl disabled:opacity-40 hover:opacity-90 transition-opacity"
      >
        {loading ? <RefreshCw size={16} className="animate-spin" /> : <Microscope size={16} />}
        {loading ? "Running Forensic Analysis…" : "Run Full FRI Analysis"}
      </button>
    </div>
  );
}

// ── FRI Score Panel ───────────────────────────────────────────────────────────

function FRIScorePanel({ sessionId, columns }: { sessionId: string; columns: string[] }) {
  const [result, setResult] = useState<FRIResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "high" | "review" | "low">("all");

  const runFRI = async (cfg: {
    investigator_col: string;
    time_col: string;
    metric_cols: string[];
    shared_attr_cols: string[];
  }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post(`/api/clinical/fri/${sessionId}`, cfg);
      setResult(res.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } };
      setError(e?.response?.data?.error ?? "FRI analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = () => {
    window.open(`${API_BASE}/api/download_report/${sessionId}`, "_blank");
  };

  const investigators = result
    ? Object.values(result.investigators).filter(
      inv => filter === "all" || inv.risk_band === filter
    )
    : [];

  const summary = result?.summary;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-black tracking-tight text-white mb-1">
            Fabrication Risk Index <span className="text-purple-400">Dashboard</span>
          </h2>
          <p className="text-neutral-500 text-sm">
            7-layer forensic scoring per investigator — the core patentable output of ClinicalSentinel
          </p>
        </div>
        {result && (
          <div className="flex gap-4 items-center flex-wrap">
            <button
              onClick={handleDownloadReport}
              className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors text-sm font-medium shadow-lg shadow-blue-500/20"
            >
              <FileText className="w-4 h-4" />
              Export FDA 21 CFR PDF
            </button>
            <div className="flex gap-2 text-xs border-l border-white/10 pl-4">
              {(["all", "high", "review", "low"] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-all capitalize ${
                    filter === f ? "bg-white text-black" : "bg-white/5 text-neutral-400 hover:text-white"
                  }`}
                >
                  {f === "all" ? "All" : f === "high" ? "🔴 High Risk" : f === "review" ? "🟡 Review" : "🟢 Clean"}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <ColumnMapper columns={columns} onRun={runFRI} loading={loading} />

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
          {error}
        </div>
      )}

      {summary && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3"
        >
          {[
            { label: "Investigators",    value: summary.total_investigators, icon: <FlaskConical size={14} />, color: "text-white" },
            { label: "High Risk 🔴",     value: summary.high_risk_count,    icon: <AlertTriangle size={14} />, color: "text-red-400" },
            { label: "Needs Review 🟡",  value: summary.needs_review_count, icon: <Clock size={14} />,         color: "text-amber-400" },
            { label: "Low Risk 🟢",      value: summary.low_risk_count,     icon: <Shield size={14} />,        color: "text-emerald-400" },
            { label: "Peak FRI",         value: summary.highest_fri,        icon: <Activity size={14} />,      color: "text-rose-400" },
            { label: "Mean FRI",         value: summary.mean_fri,           icon: <BarChart2 size={14} />,     color: "text-purple-400" },
          ].map(({ label, value, icon, color }) => (
            <div key={label} className="bg-white/[0.03] border border-white/5 rounded-xl p-4 text-center">
              <div className="flex items-center justify-center gap-1 text-xs text-neutral-500 mb-2">
                {icon} {label}
              </div>
              <p className={`font-black text-2xl ${color} font-mono`}>{value}</p>
            </div>
          ))}
        </motion.div>
      )}

      {result && investigators.length === 0 && (
        <div className="text-center py-12 text-neutral-500">
          No investigators match the selected filter.
        </div>
      )}

      <div className="space-y-3">
        <AnimatePresence>
          {investigators.map((inv, i) => (
            <motion.div
              key={inv.investigator_id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <InvestigatorCard data={inv} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {!result && !loading && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-20 h-20 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-6">
            <Microscope className="w-10 h-10 text-purple-400" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Ready for Forensic Analysis</h3>
          <p className="text-neutral-500 max-w-sm">
            Map your columns above and run the full FRI analysis to score every investigator across all 7 forensic layers.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Tab Configuration ─────────────────────────────────────────────────────────

type ForensicTab = "fri" | "investi" | "advanced" | "collusion" | "regrag";

const TABS: { id: ForensicTab; label: string; icon: React.ReactNode; badge?: string }[] = [
  { id: "fri",      label: "FRI Scores",         icon: <Microscope size={14} />,  badge: "7-Layer" },
  { id: "investi",  label: "InvestiProfile",     icon: <Brain size={14} />,       badge: "F7" },
  { id: "advanced", label: "Deep Analysis",      icon: <Activity size={14} />,    badge: "F3·F5·F6" },
  { id: "collusion",label: "Collusion Network",  icon: <Network size={14} />,     badge: "F2 GNN" },
  { id: "regrag",   label: "RegRAG Compliance",  icon: <Scale size={14} />,       badge: "F4" },
];

// ── Main Component ────────────────────────────────────────────────────────────

export default function FRIDashboard({ sessionId, columns }: Props) {
  const [activeTab, setActiveTab] = useState<ForensicTab>("fri");

  return (
    <div className="space-y-0">
      {/* ── Tab Bar ── */}
      <div className="flex gap-1 mb-6 bg-white/[0.02] border border-white/5 rounded-2xl p-1.5 overflow-x-auto">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all whitespace-nowrap ${
              activeTab === tab.id
                ? "bg-gradient-to-r from-purple-600/80 to-indigo-600/80 text-white shadow-lg"
                : "text-neutral-500 hover:text-neutral-200 hover:bg-white/5"
            }`}
          >
            {tab.icon}
            {tab.label}
            {tab.badge && (
              <span className={`text-xs px-1.5 py-0.5 rounded-md font-mono ${
                activeTab === tab.id ? "bg-white/20 text-white" : "bg-white/5 text-neutral-600"
              }`}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Panel Content ── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.18 }}
        >
          {activeTab === "fri"       && <FRIScorePanel sessionId={sessionId} columns={columns} />}
          {activeTab === "investi"   && <InvestiProfile sessionId={sessionId} columns={columns} />}
          {activeTab === "advanced"  && <AdvancedIntelligence sessionId={sessionId} columns={columns} />}
          {activeTab === "collusion" && <CollusionNetwork sessionId={sessionId} columns={columns} />}
          {activeTab === "regrag"    && <RegRagCompliance sessionId={sessionId} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
