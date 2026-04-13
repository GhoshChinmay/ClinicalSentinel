"use client";

import React, { useEffect, useState, useCallback } from "react";
import api from "@/services/api.service";
import type {
    InsightsDashboardResponse,
    ColumnProfile,
    CorrelationEntry,
} from "@/types/api";
import {
    Brain,
    AlertTriangle,
    Database,
    Columns3,
    Hash,
    Type,
    ShieldAlert,
    HeartPulse,
    TrendingUp,
    TrendingDown,
    BarChart3,
    Sparkles,
    RefreshCcw,
    ChevronDown,
    ChevronUp,
} from "lucide-react";
import { motion } from "framer-motion";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Legend,
} from "recharts";

// ── Design Tokens ─────────────────────────────────────────────
const ACCENT = {
    purple: { bg: "rgba(147,51,234,0.12)", border: "rgba(147,51,234,0.25)", text: "#a78bfa" },
    cyan: { bg: "rgba(6,182,212,0.12)", border: "rgba(6,182,212,0.25)", text: "#67e8f9" },
    emerald: { bg: "rgba(16,185,129,0.12)", border: "rgba(16,185,129,0.25)", text: "#6ee7b7" },
    amber: { bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.25)", text: "#fbbf24" },
    rose: { bg: "rgba(244,63,94,0.12)", border: "rgba(244,63,94,0.25)", text: "#fb7185" },
};

const PIE_COLORS = ["#8b5cf6", "#06b6d4", "#f59e0b"];

// ── Animated Counter Hook ─────────────────────────────────────
function useAnimatedValue(target: number, duration = 800) {
    const [value, setValue] = useState(0);
    useEffect(() => {
        if (target === 0) { requestAnimationFrame(() => setValue(0)); return; }
        const start = performance.now();
        const step = (now: number) => {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setValue(Math.round(eased * target));
            if (progress < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }, [target, duration]);
    return value;
}

// ── Sub-Components ────────────────────────────────────────────

function KPICard({ icon, label, value, suffix, accent, delay }: {
    icon: React.ReactNode; label: string; value: number; suffix?: string;
    accent: typeof ACCENT.purple; delay: number;
}) {
    const animated = useAnimatedValue(value);
    return (
        <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay }}
            className="relative overflow-hidden rounded-2xl border p-5 backdrop-blur-xl"
            style={{ background: accent.bg, borderColor: accent.border }}
        >
            <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-20 blur-2xl" style={{ background: accent.text }} />
            <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-xl" style={{ background: accent.bg }}>
                    {icon}
                </div>
                <span className="text-xs font-bold uppercase tracking-widest text-neutral-400">{label}</span>
            </div>
            <p className="text-3xl font-black text-white tabular-nums">
                {animated.toLocaleString()}{suffix && <span className="text-lg font-medium text-neutral-400 ml-1">{suffix}</span>}
            </p>
        </motion.div>
    );
}

function SectionHeader({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle: string }) {
    return (
        <div className="flex items-center gap-3 mb-5">
            <div className="p-2 rounded-xl bg-white/5 border border-white/10">{icon}</div>
            <div>
                <h3 className="text-lg font-bold text-white">{title}</h3>
                <p className="text-xs text-neutral-500">{subtitle}</p>
            </div>
        </div>
    );
}

function TypeBreakdownChart({ data }: { data: { name: string; value: number }[] }) {
    const total = data.reduce((s, d) => s + d.value, 0);
    if (total === 0) return null;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 backdrop-blur-xl"
        >
            <SectionHeader icon={<Columns3 className="w-4 h-4 text-purple-400" />} title="Column Type Distribution" subtitle="Breakdown of feature types in your dataset" />
            <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie data={data} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={4} dataKey="value" animationBegin={200} animationDuration={800}>
                            {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: "12px", fontSize: "13px" }} />
                        <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: "12px", color: "#999" }} />
                    </PieChart>
                </ResponsiveContainer>
            </div>
        </motion.div>
    );
}

function MissingDataChart({ data }: { data: { column: string; null_pct: number }[] }) {
    if (!data.length) return null;
    const chartData = data.slice(0, 8).map(d => ({
        name: d.column.length > 18 ? d.column.slice(0, 16) + "…" : d.column,
        value: d.null_pct,
        fullName: d.column,
    }));

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 backdrop-blur-xl"
        >
            <SectionHeader icon={<BarChart3 className="w-4 h-4 text-amber-400" />} title="Missing Data Hotspots" subtitle="Columns with the highest null percentages" />
            <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 20 }}>
                        <XAxis type="number" domain={[0, "auto"]} tickFormatter={(v: unknown) => `${v}%`} tick={{ fill: "#666", fontSize: 11 }} axisLine={false} />
                        <YAxis type="category" dataKey="name" width={120} tick={{ fill: "#999", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <Tooltip
                            contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: "12px", fontSize: "13px" }}
                            formatter={(v: unknown) => [`${Number(v).toFixed(2)}%`, "Missing"]}
                        />
                        <Bar dataKey="value" radius={[0, 6, 6, 0]} animationDuration={800}>
                            {chartData.map((_, i) => {
                                const pct = chartData[i].value;
                                const color = pct > 5 ? "#f43f5e" : pct > 1 ? "#f59e0b" : "#10b981";
                                return <Cell key={i} fill={color} />;
                            })}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </motion.div>
    );
}

function AnomalyDistChart({ data }: { data: { column: string; anomaly_count: number }[] }) {
    if (!data.length) return null;
    const chartData = data.slice(0, 8).map(d => ({
        name: d.column.length > 15 ? d.column.slice(0, 13) + "…" : d.column,
        count: d.anomaly_count,
    }));

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 backdrop-blur-xl"
        >
            <SectionHeader icon={<ShieldAlert className="w-4 h-4 text-rose-400" />} title="Anomaly Distribution" subtitle="Columns driving the most flagged anomalies" />
            <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ left: -10, right: 10 }}>
                        <XAxis dataKey="name" tick={{ fill: "#999", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fill: "#666", fontSize: 11 }} axisLine={false} />
                        <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: "12px", fontSize: "13px" }} />
                        <defs>
                            <linearGradient id="anomGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.9} />
                                <stop offset="100%" stopColor="#f43f5e" stopOpacity={0.3} />
                            </linearGradient>
                        </defs>
                        <Bar dataKey="count" fill="url(#anomGrad)" radius={[6, 6, 0, 0]} animationDuration={800} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </motion.div>
    );
}

function CorrelationCards({ correlations }: { correlations: CorrelationEntry[] }) {
    if (!correlations.length) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 backdrop-blur-xl"
        >
            <SectionHeader icon={<TrendingUp className="w-4 h-4 text-cyan-400" />} title="Top Correlations" subtitle="Strongest feature relationships detected" />
            <div className="space-y-3">
                {correlations.slice(0, 6).map((c, i) => {
                    const isPositive = c.value > 0;
                    const strength = Math.abs(c.value);
                    const barColor = isPositive ? "#06b6d4" : "#f43f5e";
                    return (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.6 + i * 0.08 }}
                            className="flex items-center gap-3"
                        >
                            <div className="flex items-center gap-1.5 min-w-[180px]">
                                <span className="text-sm text-neutral-300 font-medium truncate max-w-[80px]">{c.col_a}</span>
                                <span className="text-neutral-600">↔</span>
                                <span className="text-sm text-neutral-300 font-medium truncate max-w-[80px]">{c.col_b}</span>
                            </div>
                            <div className="flex-1 h-2 bg-neutral-800 rounded-full overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${strength * 100}%` }}
                                    transition={{ duration: 0.8, delay: 0.7 + i * 0.08 }}
                                    className="h-full rounded-full"
                                    style={{ background: barColor }}
                                />
                            </div>
                            <div className="flex items-center gap-1 min-w-[60px] justify-end">
                                {isPositive ? <TrendingUp className="w-3 h-3 text-cyan-400" /> : <TrendingDown className="w-3 h-3 text-rose-400" />}
                                <span className="text-xs font-mono font-bold" style={{ color: barColor }}>
                                    {c.value > 0 ? "+" : ""}{c.value.toFixed(3)}
                                </span>
                            </div>
                        </motion.div>
                    );
                })}
            </div>
        </motion.div>
    );
}

function ColumnProfileCards({ profiles }: { profiles: ColumnProfile[] }) {
    const [expanded, setExpanded] = useState(false);
    const numericProfiles = profiles.filter(p => p.type === "numeric");
    const textProfiles = profiles.filter(p => p.type === "text");
    const displayCount = expanded ? numericProfiles.length : Math.min(6, numericProfiles.length);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
        >
            <SectionHeader icon={<Hash className="w-4 h-4 text-emerald-400" />} title="Column Profiles" subtitle="Statistical fingerprint for each feature" />

            {/* Numeric Columns */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                {numericProfiles.slice(0, displayCount).map((p, i) => (
                    <motion.div
                        key={p.name}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.7 + i * 0.06 }}
                        className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4 hover:border-emerald-500/30 transition-colors"
                    >
                        <div className="flex justify-between items-start mb-3">
                            <div className="flex items-center gap-2">
                                <Hash className="w-3.5 h-3.5 text-emerald-400" />
                                <span className="text-sm font-bold text-white truncate max-w-[140px]">{p.name}</span>
                            </div>
                            {(p.outlier_count ?? 0) > 0 && (
                                <span className="px-2 py-0.5 text-[10px] font-bold bg-rose-500/20 text-rose-400 rounded-full">
                                    {p.outlier_count} outliers
                                </span>
                            )}
                        </div>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                            <div className="flex justify-between"><span className="text-neutral-500">Min</span><span className="text-neutral-300 font-mono">{p.min?.toLocaleString() ?? "—"}</span></div>
                            <div className="flex justify-between"><span className="text-neutral-500">Max</span><span className="text-neutral-300 font-mono">{p.max?.toLocaleString() ?? "—"}</span></div>
                            <div className="flex justify-between"><span className="text-neutral-500">Mean</span><span className="text-neutral-300 font-mono">{p.mean?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ?? "—"}</span></div>
                            <div className="flex justify-between"><span className="text-neutral-500">Std</span><span className="text-neutral-300 font-mono">{p.std?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ?? "—"}</span></div>
                            <div className="flex justify-between"><span className="text-neutral-500">Median</span><span className="text-neutral-300 font-mono">{p.median?.toLocaleString(undefined, { maximumFractionDigits: 2 }) ?? "—"}</span></div>
                            <div className="flex justify-between"><span className="text-neutral-500">Skew</span><span className={`font-mono ${Math.abs(p.skewness ?? 0) > 2 ? "text-amber-400" : "text-neutral-300"}`}>{p.skewness ?? "—"}</span></div>
                        </div>
                        {(p.null_count ?? 0) > 0 && (
                            <div className="mt-2 pt-2 border-t border-neutral-800 text-xs text-amber-400/80">
                                ⚠ {p.null_count} nulls ({p.null_pct}%)
                            </div>
                        )}
                    </motion.div>
                ))}
            </div>

            {numericProfiles.length > 6 && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="flex items-center gap-2 mx-auto px-4 py-2 text-xs font-bold text-neutral-400 hover:text-white transition-colors bg-neutral-900/40 rounded-xl border border-neutral-800 hover:border-neutral-700"
                >
                    {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    {expanded ? "Show Less" : `Show All ${numericProfiles.length} Columns`}
                </button>
            )}

            {/* Text Columns Summary */}
            {textProfiles.length > 0 && (
                <div className="mt-6">
                    <div className="flex items-center gap-2 mb-3">
                        <Type className="w-3.5 h-3.5 text-purple-400" />
                        <span className="text-sm font-bold text-neutral-300">Text Columns</span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {textProfiles.map((p, i) => (
                            <motion.div
                                key={p.name}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.8 + i * 0.05 }}
                                className="bg-neutral-900/40 border border-neutral-800 rounded-lg px-3 py-2.5"
                            >
                                <p className="text-xs font-bold text-white truncate mb-1">{p.name}</p>
                                <p className="text-[10px] text-neutral-500">{p.unique_values?.toLocaleString() ?? 0} unique • {p.null_pct}% null</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            )}
        </motion.div>
    );
}

function AINarrativeSection({ narratives }: { narratives: string[] }) {
    if (!narratives.length) return null;
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.7 }}
        >
            <SectionHeader icon={<Sparkles className="w-4 h-4 text-purple-400" />} title="AI-Generated Insights" subtitle="Groq LPU-powered analysis of your dataset statistics" />
            <div className="space-y-4">
                {narratives.map((text, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.8 + i * 0.12 }}
                        className="relative bg-neutral-900/60 border border-neutral-800 rounded-2xl p-5 pl-6 overflow-hidden group hover:border-purple-500/30 transition-colors"
                    >
                        <div className="absolute left-0 top-0 bottom-0 w-1 rounded-full" style={{
                            background: `linear-gradient(180deg, ${["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e"][i % 5]}, transparent)`,
                        }} />
                        <div className="absolute -right-8 -top-8 h-20 w-20 rounded-full opacity-0 group-hover:opacity-10 blur-2xl transition-opacity" style={{
                            background: ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e"][i % 5],
                        }} />
                        <div className="flex items-start gap-3">
                            <div className="mt-0.5 p-1.5 rounded-lg bg-white/5 shrink-0">
                                <Brain className="w-3.5 h-3.5" style={{ color: ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e"][i % 5] }} />
                            </div>
                            <p className="text-sm text-neutral-300 leading-relaxed">{text}</p>
                        </div>
                    </motion.div>
                ))}
            </div>
        </motion.div>
    );
}

// ── Main Component ────────────────────────────────────────────

interface InsightsProps {
    sessionId: string;
    cachedInsights?: InsightsDashboardResponse | null;
    onInsightsLoaded?: (data: InsightsDashboardResponse) => void;
}

export default function Insights({ sessionId, cachedInsights, onInsightsLoaded }: InsightsProps) {
    const hasCachedData = !!cachedInsights;
    const [data, setData] = useState<InsightsDashboardResponse | null>(hasCachedData ? cachedInsights : null);
    const [loading, setLoading] = useState(!hasCachedData);
    const [error, setError] = useState<string | null>(null);

    const fetchInsights = useCallback(() => {
        setLoading(true);
        setError(null);
        setData(null);

        api.get<InsightsDashboardResponse>(`/api/insights/${sessionId}`)
            .then((res) => {
                setData(res.data);
                setLoading(false);
                if (onInsightsLoaded) onInsightsLoaded(res.data);
            })
            .catch((err: unknown) => {
                const axiosErr = err as { response?: { data?: { error?: string } }; message?: string };
                setError(axiosErr.response?.data?.error || "Failed to generate insights.");
                setLoading(false);
            });
    }, [sessionId, onInsightsLoaded]);

    useEffect(() => {
        if (!hasCachedData) {
            const timer = setTimeout(() => fetchInsights(), 0);
            return () => clearTimeout(timer);
        }
    }, [fetchInsights, hasCachedData]);

    // ── Loading State ─────────────────────────────────────────
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-neutral-400 bg-neutral-900/50 border border-neutral-800 rounded-2xl">
                <div className="relative mb-6">
                    <div className="absolute inset-0 bg-purple-500 blur-xl opacity-20 rounded-full animate-pulse"></div>
                    <Brain className="w-12 h-12 text-purple-500 relative z-10 animate-bounce" />
                </div>
                <p className="text-lg font-medium text-white mb-2">Analyzing Dataset...</p>
                <p className="text-sm">Computing statistical profiles and generating AI insights.</p>
            </div>
        );
    }

    // ── Error State ───────────────────────────────────────────
    if (error) {
        return (
            <div className="bg-red-500/10 border border-red-500/20 p-6 rounded-2xl flex items-start">
                <AlertTriangle className="w-6 h-6 text-red-500 mr-4 shrink-0" />
                <div className="flex-1">
                    <h3 className="text-red-500 font-bold mb-1">Analysis Failed</h3>
                    <p className="text-red-400/80 text-sm">{error}</p>
                </div>
                <button
                    onClick={fetchInsights}
                    className="ml-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-bold rounded-xl text-sm transition-colors"
                >
                    Retry
                </button>
            </div>
        );
    }

    // ── Empty State ───────────────────────────────────────────
    if (!data) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-neutral-500 bg-neutral-900/30 rounded-2xl border border-neutral-800 border-dashed">
                <Brain className="w-10 h-10 mb-4 opacity-20" />
                <h3 className="text-lg font-bold text-white mb-1">No Insights Generated</h3>
                <p className="text-sm mb-4 max-w-md text-center">The analysis engine could not process this dataset. Please check your Groq API key and try again.</p>
                <button
                    onClick={fetchInsights}
                    className="px-5 py-2.5 bg-white text-black font-bold rounded-xl hover:bg-neutral-200 transition-colors text-sm"
                >
                    Retry Analysis
                </button>
            </div>
        );
    }

    // ── Dashboard ─────────────────────────────────────────────
    const { summary, column_profiles, missing_data_map, type_breakdown, top_correlations, anomaly_distribution, ai_narrative } = data;

    const pieData = [
        { name: "Numeric", value: type_breakdown.numeric },
        { name: "Text", value: type_breakdown.text },
        { name: "Date", value: type_breakdown.date },
    ].filter(d => d.value > 0);

    return (
        <div className="w-full space-y-8">
            {/* ── KPI Hero Bar (Updated to 3 columns) ────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <KPICard icon={<Database className="w-5 h-5" style={{ color: ACCENT.purple.text }} />} label="Total Rows" value={summary.total_rows} accent={ACCENT.purple} delay={0.05} />
                <KPICard icon={<Columns3 className="w-5 h-5" style={{ color: ACCENT.cyan.text }} />} label="Columns" value={summary.total_columns} accent={ACCENT.cyan} delay={0.1} />
                <KPICard icon={<ShieldAlert className="w-5 h-5" style={{ color: ACCENT.rose.text }} />} label="Anomalies" value={summary.anomaly_count} suffix={`(${summary.anomaly_rate}%)`} accent={ACCENT.rose} delay={0.15} />
            </div>

            {/* ── Charts Row ─────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <TypeBreakdownChart data={pieData} />
                {missing_data_map.length > 0 ? (
                    <MissingDataChart data={missing_data_map} />
                ) : (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.6, delay: 0.4 }}
                        className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 backdrop-blur-xl flex flex-col items-center justify-center text-center"
                    >
                        <div className="p-3 rounded-full bg-emerald-500/10 mb-3">
                            <HeartPulse className="w-8 h-8 text-emerald-400" />
                        </div>
                        <h3 className="text-white font-bold mb-1">Zero Missing Data</h3>
                        <p className="text-xs text-neutral-500 max-w-xs">Excellent! No null values were detected in any column of your dataset.</p>
                    </motion.div>
                )}
            </div>

            {/* ── Anomaly Distribution + Correlations ─────────── */}
            {(anomaly_distribution.length > 0 || top_correlations.length > 0) && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <AnomalyDistChart data={anomaly_distribution} />
                    <CorrelationCards correlations={top_correlations} />
                </div>
            )}

            {/* ── Column Profiles ────────────────────────────────── */}
            {column_profiles.length > 0 && <ColumnProfileCards profiles={column_profiles} />}

            {/* ── AI Narrative ────────────────────────────────────── */}
            <AINarrativeSection narratives={ai_narrative} />

            {/* ── Refresh Button ──────────────────────────────────── */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.0 }}
                className="flex justify-center pt-4"
            >
                <button
                    onClick={fetchInsights}
                    className="flex items-center gap-2 px-5 py-2.5 text-sm font-bold text-neutral-400 hover:text-white bg-neutral-900/50 hover:bg-neutral-800 rounded-xl border border-neutral-800 hover:border-neutral-700 transition-all"
                >
                    <RefreshCcw className="w-4 h-4" />
                    Regenerate Insights
                </button>
            </motion.div>
        </div>
    );
}
