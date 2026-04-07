"use client";

import React, { useEffect, useState } from "react";
import api from '@/lib/api';
import type { VizData } from '@/types/api';
import { BarChart2, Activity, ShieldCheck, Loader2, Navigation, AlignLeft } from "lucide-react";
import { motion } from "framer-motion";
import VisualizerScatterPlot from "./VisualizerScatterPlot";

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
                // FE-03 FIX: Backend returns {error: "..."} not {detail: "..."}
                setError(err.response?.data?.error || err.response?.data?.detail || "Failed to load visualization data.");
                setLoading(false);
            });
    }, [sessionId]);

    // scatter plots and correlation logic moved to VisualizerScatterPlot

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
                <VisualizerScatterPlot 
                    data={data} 
                    varX={varX} 
                    varY={varY} 
                    setVarX={setVarX} 
                    setVarY={setVarY} 
                />
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