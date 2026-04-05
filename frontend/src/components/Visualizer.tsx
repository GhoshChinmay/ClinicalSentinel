"use client";

import React, { useEffect, useState, useMemo } from "react";
import api from '@/lib/api';
import type { VizData } from '@/types/api';
import { BarChart2, Activity, ShieldCheck, Loader2, Navigation, Zap, AlignLeft } from "lucide-react";
import { motion } from "framer-motion";

interface VizProps {
    sessionId: string;
}

export default function Visualizer({ sessionId }: VizProps) {
    const [data, setData] = useState<VizData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'distribution' | 'correlation' | 'categorical'>('distribution');

    const [varX, setVarX] = useState<string>('');
    const [varY, setVarY] = useState<string>('');
    const [selectedCatCol, setSelectedCatCol] = useState<string>('');

    useEffect(() => {
        api.get<VizData>(`/api/viz/${sessionId}`)
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

                setLoading(false);
            })
            .catch((err) => {
                setError(err.response?.data?.detail || "Failed to load visualization data.");
                setLoading(false);
            });
    }, [sessionId]);

    const scatterData = useMemo(() => {
        if (!data || !data.clean_sample || !varX || !varY || data.columns.length < 2) return null;

        const points = data.clean_sample
            .map((row: Record<string, unknown>) => ({ x: Number(row[varX]), y: Number(row[varY]) }))
            .filter((p: { x: number; y: number }) => Number.isFinite(p.x) && Number.isFinite(p.y));

        if (points.length === 0) return null;

        const xValues = points.map((p: { x: number }) => p.x);
        const yValues = points.map((p: { y: number }) => p.y);
        const xMin = Math.min(...xValues);
        const xMax = Math.max(...xValues);
        const yMin = Math.min(...yValues);
        const yMax = Math.max(...yValues);

        const n = points.length;
        const meanX = xValues.reduce((a: number, b: number) => a + b, 0) / n;
        const meanY = yValues.reduce((a: number, b: number) => a + b, 0) / n;

        let ssXY = 0, ssXX = 0;
        for (let i = 0; i < n; i++) {
            ssXY += (points[i].x - meanX) * (points[i].y - meanY);
            ssXX += (points[i].x - meanX) ** 2;
        }

        const slope = ssXX === 0 ? 0 : ssXY / ssXX;
        const intercept = meanY - slope * meanX;

        let rValue = 0;
        if (data.correlation && data.correlation.features) {
            const xIdx = data.correlation.features.indexOf(varX);
            const yIdx = data.correlation.features.indexOf(varY);
            if (xIdx !== -1 && yIdx !== -1) rValue = data.correlation.matrix[yIdx][xIdx];
        }

        return { points, xMin, xMax, yMin, yMax, slope, intercept, rValue };
    }, [data, varX, varY]);

    const getCorrelationBadge = (r: number) => {
        const abs = Math.abs(r);
        const dir = r < 0 ? "Negative" : "Positive";
        if (abs >= 0.7) return { text: `Strong ${dir}`, color: r < 0 ? 'text-red-400 bg-red-500/10 border-red-500/30' : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' };
        if (abs >= 0.3) return { text: `Moderate ${dir}`, color: 'text-blue-400 bg-blue-500/10 border-blue-500/30' };
        if (abs > 0.1) return { text: `Weak ${dir}`, color: 'text-neutral-400 bg-neutral-800 border-neutral-700' };
        return { text: "Neutral / No Correlation", color: 'text-neutral-500 bg-black border-neutral-800' };
    };

    if (loading) return <div className="flex flex-col items-center justify-center py-20 text-neutral-400"><Loader2 className="w-8 h-8 animate-spin text-purple-500 mb-4" /><p>Calculating global distribution matrices...</p></div>;
    if (error) return <div className="text-red-500 bg-red-500/10 p-4 rounded-xl border border-red-500/20">{error}</div>;
    if (!data) return null;

    const hasNumeric = data.global_raw_hist && data.global_raw_hist.length > 0;
    const hasCategorical = data.categorical_data && data.categorical_data.length > 0;

    const maxRaw = hasNumeric ? Math.max(...data.global_raw_hist.map((d: { count: number }) => d.count)) : 0;
    const maxClean = data.global_clean_hist && hasNumeric ? Math.max(...data.global_clean_hist.map((d: { count: number }) => d.count)) : maxRaw;
    const absoluteMax = Math.max(maxRaw, maxClean);
    const healthScore = data.health_score ?? (data.global_clean_hist && data.global_clean_hist.length > 0 ? 98 : 45);

    // --- TYpescript Fix: Optional Chaining added here ---
    const activeCatData = data?.categorical_data?.find((c: { column: string }) => c.column === selectedCatCol);
    const maxCatCount = activeCatData?.top_values ? Math.max(...activeCatData.top_values.map((v: { count: number }) => v.count)) : 0;

    return (
        <div className="w-full space-y-6">
            <div className="flex p-1 bg-neutral-900 border border-neutral-800 rounded-xl w-fit mx-auto mb-8">
                {hasNumeric && (
                    <>
                        <button onClick={() => setActiveTab('distribution')} className={`flex items-center px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === 'distribution' ? 'bg-neutral-800 text-white shadow-md' : 'text-neutral-500 hover:text-neutral-300'}`}>
                            <BarChart2 className="w-4 h-4 mr-2" /> Distribution Curve
                        </button>
                        <button onClick={() => setActiveTab('correlation')} className={`flex items-center px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === 'correlation' ? 'bg-neutral-800 text-white shadow-md' : 'text-neutral-500 hover:text-neutral-300'}`}>
                            <Navigation className="w-4 h-4 mr-2" /> Pairwise Scatter
                        </button>
                    </>
                )}
                {hasCategorical && (
                    <button onClick={() => setActiveTab('categorical')} className={`flex items-center px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === 'categorical' ? 'bg-neutral-800 text-white shadow-md' : 'text-neutral-500 hover:text-neutral-300'}`}>
                        <AlignLeft className="w-4 h-4 mr-2" /> Text & Categories
                    </button>
                )}
            </div>

            {/* TAB 1: DISTRIBUTION CURVE (Numeric Only) */}
            {activeTab === 'distribution' && hasNumeric && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-neutral-900 border border-neutral-800 p-6 rounded-2xl flex flex-col justify-center">
                            <div className="flex items-center text-neutral-400 mb-2"><Activity className="w-5 h-5 mr-2 text-blue-500" /> Numeric Features</div>
                            <p className="text-3xl font-black text-white">{data.columns.length}</p>
                        </div>
                        <div className="bg-neutral-900 border border-neutral-800 p-6 rounded-2xl flex flex-col justify-center">
                            <div className="flex items-center text-neutral-400 mb-2"><BarChart2 className="w-5 h-5 mr-2 text-purple-500" /> Distribution Spread</div>
                            <p className="text-3xl font-black text-white">±5σ</p>
                        </div>
                        <div className="bg-emerald-500/10 border border-emerald-500/30 p-6 rounded-2xl flex flex-col justify-center relative overflow-hidden">
                            <div className="absolute -right-4 -top-4 w-24 h-24 bg-emerald-500/20 rounded-full blur-2xl"></div>
                            <div className="flex items-center text-emerald-400 mb-2 font-bold"><ShieldCheck className="w-5 h-5 mr-2" /> Data Health Score</div>
                            <p className="text-4xl font-black text-emerald-400">{healthScore}%</p>
                        </div>
                    </div>

                    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-8">
                        <div className="flex items-center justify-between mb-8">
                            <div>
                                <h3 className="text-xl font-bold text-white">Global Statistical Distribution</h3>
                                <p className="text-sm text-neutral-500 mt-1">Comparing the Z-Score normalization before and after AI sanitization.</p>
                            </div>
                            <div className="flex items-center space-x-4 text-sm font-medium">
                                <div className="flex items-center"><div className="w-3 h-3 rounded-full bg-red-500/50 mr-2"></div> Raw Data</div>
                                <div className="flex items-center"><div className="w-3 h-3 rounded-full bg-emerald-500 mr-2 shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div> Cleaned Data</div>
                            </div>
                        </div>

                        <div className="relative w-full h-[300px] flex items-end justify-between space-x-1">
                            {data.global_raw_hist.map((rawBin: { bin: string; count: number }, idx: number) => {
                                const cleanBin = data.global_clean_hist ? data.global_clean_hist[idx] : null;
                                const rawHeight = Math.max((rawBin.count / absoluteMax) * 100, 1);
                                const cleanHeight = cleanBin ? Math.max((cleanBin.count / absoluteMax) * 100, 1) : 0;
                                return (
                                    <div key={idx} className="relative flex-1 flex flex-col items-center group h-full justify-end">
                                        <motion.div initial={{ height: 0 }} animate={{ height: `${rawHeight}%` }} transition={{ duration: 0.8, delay: idx * 0.02 }} className="absolute bottom-0 w-full bg-red-500/30 rounded-t-sm"></motion.div>
                                        {cleanBin && <motion.div initial={{ height: 0 }} animate={{ height: `${cleanHeight}%` }} transition={{ duration: 0.8, delay: 0.5 + (idx * 0.02) }} className="absolute bottom-0 w-full bg-emerald-500/80 rounded-t-sm shadow-[0_-2px_10px_rgba(16,185,129,0.2)]"></motion.div>}
                                        <div className="opacity-0 group-hover:opacity-100 absolute -top-12 bg-black text-white text-xs py-1 px-2 rounded border border-neutral-800 pointer-events-none whitespace-nowrap z-10 transition-opacity">
                                            Bin: {rawBin.bin} <br /> Raw: {rawBin.count} | Clean: {cleanBin ? cleanBin.count : 'N/A'}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        <div className="flex justify-between mt-4 text-xs font-bold text-neutral-600">
                            <span>Extreme Low (-5σ)</span>
                            <span>Average (0σ)</span>
                            <span>Extreme High (+5σ)</span>
                        </div>
                    </div>
                </motion.div>
            )}

            {/* TAB 2: SCATTER PLOT (Numeric Only) */}
            {activeTab === 'correlation' && hasNumeric && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-8">
                    <div className="flex flex-col md:flex-row md:items-start justify-between mb-8 gap-6">
                        <div>
                            <h3 className="text-xl font-bold text-white mb-1">Pairwise Scatter Explorer</h3>
                            <p className="text-sm text-neutral-400">Select two variables to plot their actual data points and reveal hidden trends.</p>
                        </div>

                        {scatterData && (
                            <div className="flex items-center space-x-4 bg-black/40 border border-neutral-800 p-4 rounded-xl shrink-0">
                                <div>
                                    <div className="text-[10px] text-neutral-500 uppercase font-bold tracking-wider mb-1">Pearson Correlation (r)</div>
                                    <div className="text-2xl font-mono text-white leading-none">{scatterData.rValue.toFixed(4)}</div>
                                </div>
                                <div className={`px-4 py-2 rounded-lg border text-sm font-bold ${getCorrelationBadge(scatterData.rValue).color}`}>
                                    {getCorrelationBadge(scatterData.rValue).text}
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                        <div>
                            <label className="block text-xs font-bold text-neutral-500 uppercase mb-2">Variable X (Horizontal Axis)</label>
                            <select
                                value={varX}
                                onChange={(e) => setVarX(e.target.value)}
                                className="w-full bg-neutral-950 border border-neutral-800 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                            >
                                {data.columns.map((col: string) => <option key={col} value={col}>{col}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-neutral-500 uppercase mb-2">Variable Y (Vertical Axis)</label>
                            <select
                                value={varY}
                                onChange={(e) => setVarY(e.target.value)}
                                className="w-full bg-neutral-950 border border-neutral-800 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                            >
                                {data.columns.map((col: string) => <option key={col} value={col}>{col}</option>)}
                            </select>
                        </div>
                    </div>

                    {!scatterData ? (
                        <div className="py-20 text-center text-neutral-500 flex flex-col items-center bg-black/20 rounded-xl border border-neutral-800/50">
                            <Zap className="w-12 h-12 mb-4 opacity-20" />
                            <p>Cannot generate plot. Ensure variables have valid numeric data.</p>
                        </div>
                    ) : (
                        <div className="relative w-full aspect-[2/1] bg-[#0A0A0A] border border-neutral-800 rounded-xl overflow-hidden">
                            <svg viewBox="0 0 800 400" className="w-full h-full">
                                {/* Grid Lines */}
                                <line x1={40} y1={40} x2={40} y2={360} stroke="#262626" strokeWidth="1" />
                                <line x1={40} y1={360} x2={760} y2={360} stroke="#262626" strokeWidth="1" />

                                {/* Data Points (Dots) */}
                                {scatterData.points.map((p: { x: number; y: number }, i: number) => {
                                    const cx = 40 + ((p.x - scatterData.xMin) / (scatterData.xMax - scatterData.xMin || 1)) * 720;
                                    const cy = 360 - ((p.y - scatterData.yMin) / (scatterData.yMax - scatterData.yMin || 1)) * 320;

                                    return (
                                        <motion.circle
                                            key={i}
                                            initial={{ cx, cy: 200, opacity: 0 }}
                                            animate={{ cx, cy, opacity: 0.6 }}
                                            transition={{ duration: 0.5, delay: Math.random() * 0.2 }}
                                            r="3"
                                            fill="#60A5FA"
                                            className="hover:opacity-100 hover:fill-white transition-all cursor-crosshair"
                                        >
                                            <title>X: {p.x.toFixed(2)} | Y: {p.y.toFixed(2)}</title>
                                        </motion.circle>
                                    );
                                })}

                                {/* Line of Best Fit */}
                                {(() => {
                                    const { xMin, xMax, slope, intercept } = scatterData;
                                    const x1 = 40;
                                    const y1 = 360 - (((slope * xMin + intercept) - scatterData.yMin) / (scatterData.yMax - scatterData.yMin || 1)) * 320;
                                    const x2 = 760;
                                    const y2 = 360 - (((slope * xMax + intercept) - scatterData.yMin) / (scatterData.yMax - scatterData.yMin || 1)) * 320;

                                    return (
                                        <motion.line
                                            initial={{ pathLength: 0, opacity: 0 }}
                                            animate={{ pathLength: 1, opacity: 1 }}
                                            transition={{ duration: 1, delay: 0.5 }}
                                            x1={x1} y1={y1} x2={x2} y2={y2}
                                            stroke={scatterData.rValue < 0 ? "#F87171" : "#34D399"}
                                            strokeWidth="3"
                                            strokeDasharray="8 4"
                                        />
                                    );
                                })()}
                            </svg>

                            {/* Axis Labels */}
                            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-[10px] font-bold text-neutral-500 uppercase tracking-widest">{varX}</div>
                            <div className="absolute top-1/2 left-2 -translate-y-1/2 -rotate-90 origin-left text-[10px] font-bold text-neutral-500 uppercase tracking-widest whitespace-nowrap">{varY}</div>
                        </div>
                    )}
                </motion.div>
            )}

            {/* TAB 3: TEXT & CATEGORICAL */}
            {activeTab === 'categorical' && hasCategorical && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-8">
                        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
                            <div>
                                <h3 className="text-xl font-bold text-white">Categorical Frequency</h3>
                                <p className="text-sm text-neutral-500 mt-1">Explore the most common occurrences in your text data.</p>
                            </div>

                            <select
                                value={selectedCatCol}
                                onChange={(e) => setSelectedCatCol(e.target.value)}
                                className="w-full md:w-64 bg-neutral-950 border border-neutral-800 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                            >
                                {data.categorical_columns.map((col: string) => (
                                    <option key={col} value={col}>{col}</option>
                                ))}
                            </select>
                        </div>

                        {/* --- TYpescript Fix: Optional Chaining added here --- */}
                        {activeCatData?.top_values && (
                            <div className="space-y-4">
                                {activeCatData.top_values.map((item: { label: string; count: number }, idx: number) => {
                                    const widthPercent = Math.max((item.count / maxCatCount) * 100, 1);
                                    return (
                                        <div key={idx} className="flex items-center">
                                            <div className="w-1/3 pr-4 text-right">
                                                <span className="text-sm font-medium text-neutral-300 truncate block" title={item.label}>
                                                    {item.label === "None" || !item.label ? "[Empty/Null]" : item.label}
                                                </span>
                                            </div>
                                            <div className="w-2/3 flex items-center">
                                                <motion.div
                                                    initial={{ width: 0 }}
                                                    animate={{ width: `${widthPercent}%` }}
                                                    transition={{ duration: 0.6, delay: idx * 0.05 }}
                                                    className="h-8 bg-blue-500/20 border border-blue-500/40 rounded-r-lg relative group flex items-center"
                                                >
                                                    <span className="absolute left-full ml-3 text-xs font-bold text-blue-400 group-hover:text-white transition-colors">
                                                        {item.count.toLocaleString()}
                                                    </span>
                                                </motion.div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </motion.div>
            )}
        </div>
    );
}