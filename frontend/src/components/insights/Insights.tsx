"use client";

import React, { useEffect, useState, useCallback } from "react";
import api from "@/services/api.service";
import {
    Brain,
    AlertTriangle,
    Database,
    ShieldAlert,
    Activity,
    RefreshCcw,
    FileText,
    CheckCircle,
    Download,
    Scale,
    Gavel
} from "lucide-react";
import { motion } from "framer-motion";
import { API_BASE } from "@/constants/config";

// ── Design Tokens ─────────────────────────────────────────────
const ACCENT = {
    purple: { bg: "rgba(147,51,234,0.12)", border: "rgba(147,51,234,0.25)", text: "#a78bfa" },
    cyan: { bg: "rgba(6,182,212,0.12)", border: "rgba(6,182,212,0.25)", text: "#67e8f9" },
    emerald: { bg: "rgba(16,185,129,0.12)", border: "rgba(16,185,129,0.25)", text: "#6ee7b7" },
    amber: { bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.25)", text: "#fbbf24" },
    rose: { bg: "rgba(244,63,94,0.12)", border: "rgba(244,63,94,0.25)", text: "#fb7185" },
};

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

// ── Main Component ────────────────────────────────────────────

interface InsightsProps {
    sessionId: string;
    cachedInsights?: any;
    onInsightsLoaded?: (data: any) => void;
}

export default function Insights({ sessionId, cachedInsights, onInsightsLoaded }: InsightsProps) {
    const hasCachedData = !!cachedInsights;
    const [data, setData] = useState<any>(hasCachedData ? cachedInsights : null);
    const [loading, setLoading] = useState(!hasCachedData);
    const [error, setError] = useState<string | null>(null);

    const fetchInsights = useCallback(() => {
        setLoading(true);
        setError(null);
        setData(null);

        api.get(`/api/insights/${sessionId}`)
            .then((res) => {
                setData(res.data);
                setLoading(false);
                if (onInsightsLoaded) onInsightsLoaded(res.data);
            })
            .catch((err: unknown) => {
                const axiosErr = err as { response?: { data?: { error?: string } }; message?: string };
                setError(axiosErr.response?.data?.error || "Failed to generate regulatory insights.");
                setLoading(false);
            });
    }, [sessionId, onInsightsLoaded]);

    useEffect(() => {
        if (!hasCachedData) {
            const timer = setTimeout(() => fetchInsights(), 0);
            return () => clearTimeout(timer);
        }
    }, [fetchInsights, hasCachedData]);

    const handleDownloadPdf = () => {
        window.open(`${API_BASE}/api/download_report/${sessionId}`, "_blank");
    };

    // ── Loading State ─────────────────────────────────────────
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-neutral-400 bg-neutral-900/50 border border-neutral-800 rounded-2xl">
                <div className="relative mb-6">
                    <div className="absolute inset-0 bg-purple-500 blur-xl opacity-20 rounded-full animate-pulse"></div>
                    <Brain className="w-12 h-12 text-purple-500 relative z-10 animate-bounce" />
                </div>
                <p className="text-lg font-medium text-white mb-2">Compiling Regulatory Audit...</p>
                <p className="text-sm text-center max-w-sm">Groq LPU is cross-referencing anomalies with FDA 21 CFR Part 11 and ICH guidelines.</p>
            </div>
        );
    }

    // ── Error State ───────────────────────────────────────────
    if (error) {
        return (
            <div className="bg-red-500/10 border border-red-500/20 p-6 rounded-2xl flex items-start">
                <AlertTriangle className="w-6 h-6 text-red-500 mr-4 shrink-0" />
                <div className="flex-1">
                    <h3 className="text-red-500 font-bold mb-1">Audit Generation Failed</h3>
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
    if (!data) return null;

    // Calculate rates for the UI
    const totalRecords = data.total_records || 0;
    const flaggedRecords = data.fabrication_flags || 0;
    const flagRate = totalRecords > 0 ? ((flaggedRecords / totalRecords) * 100).toFixed(1) : "0.0";

    return (
        <div className="w-full space-y-6">

            {/* ── Header & Action Bar ───────────────────────────────── */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-neutral-900/60 border border-neutral-800 rounded-2xl backdrop-blur-xl">
                <div>
                    <h2 className="text-2xl font-black text-white flex items-center gap-3">
                        <Scale className="text-purple-500 w-6 h-6" /> Regulatory Compliance Report
                    </h2>
                    <p className="text-neutral-400 text-sm mt-1">
                        Auto-generated forensic analysis based on ICH E6(R3) and FDA guidelines.
                    </p>
                </div>
                <button
                    onClick={handleDownloadPdf}
                    className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-[0_0_20px_rgba(79,70,229,0.3)] transition-all"
                >
                    <Download className="w-5 h-5" /> Download Official PDF
                </button>
            </div>

            {/* ── KPI Hero Bar ──────────────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <KPICard icon={<Database className="w-5 h-5" style={{ color: ACCENT.cyan.text }} />} label="Total Records Scanned" value={totalRecords} accent={ACCENT.cyan} delay={0.05} />
                <KPICard icon={<ShieldAlert className="w-5 h-5" style={{ color: ACCENT.rose.text }} />} label="Fabrication Flags" value={flaggedRecords} accent={ACCENT.rose} delay={0.1} />
                <KPICard icon={<Activity className="w-5 h-5" style={{ color: ACCENT.amber.text }} />} label="Dataset Flag Rate" value={Number(flagRate)} suffix="%" accent={ACCENT.amber} delay={0.15} />
            </div>

            {/* ── Executive Summary (Groq) ──────────────────────────── */}
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.6, delay: 0.3 }}
                className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 backdrop-blur-xl relative overflow-hidden"
            >
                <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-purple-500 to-cyan-500" />
                <SectionHeader icon={<Brain className="w-5 h-5 text-purple-400" />} title="Lead Auditor Summary" subtitle="Groq AI Synthesis of Dataset Integrity" />

                <p className="text-neutral-300 leading-relaxed text-sm mb-6 pl-4 border-l border-white/5">
                    {data.summary?.executive_summary || "No executive summary generated."}
                </p>

                <div className="bg-white/5 rounded-xl p-4">
                    <h4 className="text-xs font-bold text-neutral-400 uppercase tracking-widest mb-3">Key Findings</h4>
                    <ul className="space-y-2">
                        {data.summary?.key_findings?.map((finding: string, i: number) => (
                            <li key={i} className="flex items-start gap-3 text-sm text-neutral-300">
                                <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                                <span>{finding}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </motion.div>

            {/* ── RegRAG Verdicts ───────────────────────────────────── */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.5 }}
                className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 backdrop-blur-xl"
            >
                <SectionHeader icon={<Gavel className="w-5 h-5 text-rose-400" />} title="RegRAG Statutory Violations" subtitle="Top forensic risks cross-referenced with global regulatory clauses" />

                {data.top_anomalies_xfri && data.top_anomalies_xfri.length > 0 ? (
                    <div className="space-y-4">
                        {data.top_anomalies_xfri.map((anom: any, idx: number) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: 0.6 + idx * 0.1 }}
                                className="p-5 bg-black/40 border border-neutral-800 rounded-xl hover:border-neutral-700 transition-colors"
                            >
                                <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-3">
                                    <span className="text-sm font-bold text-white flex items-center gap-2">
                                        <AlertTriangle className="w-4 h-4 text-rose-500" />
                                        High-Risk Entity #{idx + 1}
                                    </span>
                                    <span className="text-xs font-mono font-bold text-rose-400 bg-rose-500/10 px-2.5 py-1 rounded-md border border-rose-500/20">
                                        X-FRI Score: {anom.score}%
                                    </span>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* AI Reasoning */}
                                    <div>
                                        <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest block mb-1">Forensic Mechanics</span>
                                        <p className="text-sm text-neutral-400">
                                            {anom.ai_reason}
                                        </p>
                                    </div>

                                    {/* Regulatory Verdict */}
                                    <div className="bg-rose-950/20 p-4 rounded-lg border border-rose-900/30">
                                        <span className="text-[10px] font-bold text-rose-500 uppercase tracking-widest block mb-2 flex items-center gap-1.5">
                                            <FileText className="w-3 h-3" /> Legal Assessment
                                        </span>
                                        <p className="text-sm text-rose-200/90 leading-relaxed">
                                            {anom.regulatory_verdict || "No specific regulatory violation cited."}
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center p-8 bg-black/20 rounded-xl border border-dashed border-white/10">
                        <CheckCircle className="w-8 h-8 text-emerald-500 mb-2 opacity-50" />
                        <p className="text-neutral-400 text-sm">No critical statutory violations detected in this dataset.</p>
                    </div>
                )}
            </motion.div>

            {/* ── Refresh Button ──────────────────────────────────── */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8 }}
                className="flex justify-center pt-2"
            >
                <button
                    onClick={fetchInsights}
                    className="flex items-center gap-2 px-5 py-2.5 text-sm font-bold text-neutral-400 hover:text-white bg-neutral-900/50 hover:bg-neutral-800 rounded-xl border border-neutral-800 hover:border-neutral-700 transition-all"
                >
                    <RefreshCcw className="w-4 h-4" />
                    Regenerate Audit
                </button>
            </motion.div>
        </div>
    );
}