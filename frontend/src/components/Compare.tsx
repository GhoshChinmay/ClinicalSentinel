"use client";
import { useEffect, useState } from "react";
import api from '@/lib/api';
import type { CompareResponse } from '@/types/api';
import { ArrowRight, CheckCircle, AlertTriangle, Loader2, Info } from "lucide-react";

interface CompareProps {
    sessionId: string;
}

export default function Compare({ sessionId }: CompareProps) {
    const [data, setData] = useState<CompareResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        api.get<CompareResponse>(`/api/compare/${sessionId}`)
            .then((res) => {
                setData(res.data);
                setLoading(false);
            })
            .catch((err) => {
                // FE-03 FIX: Backend returns {error: "..."} not {detail: "..."}
                setError(err.response?.data?.error || err.response?.data?.detail || "Failed to fetch comparison data.");
                setLoading(false);
            });
    }, [sessionId]);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-neutral-400">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-4" />
                <p>Analyzing dataset modifications...</p>
            </div>
        );
    }

    if (error) return <div className="text-red-500 bg-red-500/10 p-4 rounded-xl border border-red-500/20">{error}</div>;
    if (!data) return null;

    if (data.is_dropped) {
        return (
            <div className="bg-green-500/10 border border-green-500/30 rounded-2xl p-10 flex flex-col items-center text-center">
                <CheckCircle className="w-16 h-16 text-green-500 mb-4" />
                <h3 className="text-2xl font-bold text-white mb-2">Anomalies Successfully Removed</h3>
                <p className="text-neutral-400 max-w-md">
                    You chose to drop or quarantine the anomalous rows. The dataset has been cleanly reduced, so there are no inline modifications to compare.
                </p>
            </div>
        );
    }

    if (data.count === 0) {
        return <p className="text-neutral-500 text-center py-10">No modifications found. The dataset was already clean.</p>;
    }

    // Ignore AI metadata columns so we only show the user their actual data
    const ignoreKeys = ["is_anomaly", "AI_Reason", "Threat_Score"];

    return (
        <div className="w-full space-y-6">
            <div className="flex items-center justify-between bg-blue-500/10 border border-blue-500/20 p-4 rounded-xl">
                <div className="flex items-center text-blue-400">
                    <Info className="w-5 h-5 mr-3" />
                    <span className="font-medium">Showing top {data.original.length} repaired rows out of {data.count} total modifications.</span>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-6">
                {data.original.map((origRow, i) => {
                    const cleanRow = data.cleaned[i];
                    if (!cleanRow) return null;
                    // Find all columns where the data actually changed
                    const changedKeys = Object.keys(origRow).filter(k => {
                        if (ignoreKeys.includes(k)) return false;
                        if (k.endsWith("_freq") || k.endsWith("_length") || k.endsWith("_digit_ratio") || k.endsWith("_upper_ratio") || k.endsWith("_special_ratio")) return false;
                        if (k.startsWith("nlp_pc")) return false;
                        if (k === "velocity_24h_sum" || k === "velocity_1h_count") return false;
                        return origRow[k] !== cleanRow[k];
                    });

                    return (
                        <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-lg overflow-hidden relative">
                            <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>

                            <h4 className="text-sm font-bold text-neutral-500 mb-4 uppercase tracking-wider">Repaired Row #{i + 1}</h4>

                            {changedKeys.length > 0 ? (
                                <div className="space-y-4">
                                    {changedKeys.map(key => (
                                        <div key={key} className="flex flex-col md:flex-row md:items-center bg-black/40 rounded-xl p-4 border border-neutral-800/50">
                                            <span className="text-neutral-400 font-medium w-48 shrink-0 mb-2 md:mb-0">{key}</span>

                                            <div className="flex items-center flex-1 min-w-0">
                                                <div className="bg-red-500/10 text-red-400 px-3 py-2 rounded-lg border border-red-500/20 flex-1 truncate line-through opacity-70">
                                                    {origRow[key] === null ? "NULL" : String(origRow[key])}
                                                </div>

                                                <ArrowRight className="w-5 h-5 text-neutral-600 mx-4 shrink-0" />

                                                <div className="bg-green-500/10 text-green-400 font-bold px-3 py-2 rounded-lg border border-green-500/20 flex-1 truncate shadow-[0_0_15px_rgba(34,197,94,0.15)]">
                                                    {cleanRow[key] === null
                                                        ? "NULL"
                                                        : typeof cleanRow[key] === 'number'
                                                            ? Number(cleanRow[key]).toFixed(2)
                                                            : String(cleanRow[key])
                                                    }
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-neutral-500 italic">No numeric values were altered in this row.</p>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}