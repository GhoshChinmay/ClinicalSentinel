"use client";

import React, { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, Brain, Eye, Zap, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";

interface OIAInsight {
    observation: string;
    insight: string;
    action: string;
}

interface InsightsProps {
    sessionId: string;
    cachedInsights?: OIAInsight[] | null;
    onInsightsLoaded?: (insights: OIAInsight[]) => void;
}

// --- KEY ALIASES: every known LLM variant for each OIA field ---
const OBSERVATION_KEYS = ['observation', 'observations', 'finding', 'findings', 'data_point', 'fact'];
const INSIGHT_KEYS = ['insight', 'insights', 'analysis', 'impact', 'interpretation', 'implication'];
const ACTION_KEYS = ['action', 'actions', 'recommendation', 'recommendations', 'recommended_action', 'recommended_actions', 'suggested_action', 'next_step', 'next_steps', 'remediation', 'resolution', 'suggestion', 'step'];

function fuzzyGet(obj: Record<string, unknown>, aliases: string[]): string {
    // Exact match first (case-insensitive)
    for (const alias of aliases) {
        const found = Object.entries(obj).find(([k]) => k.toLowerCase() === alias);
        if (found && found[1] != null && String(found[1]).trim() !== '') {
            return String(found[1]).trim();
        }
    }
    // Partial/contains match as fallback (e.g. "recommended_action" matches "action")
    for (const alias of aliases) {
        const found = Object.entries(obj).find(([k]) => k.toLowerCase().includes(alias));
        if (found && found[1] != null && String(found[1]).trim() !== '') {
            return String(found[1]).trim();
        }
    }
    return '';
}

function isOIALike(keys: string[]): boolean {
    const lower = keys.map(k => k.toLowerCase());
    return OBSERVATION_KEYS.some(k => lower.some(l => l.includes(k))) ||
           INSIGHT_KEYS.some(k => lower.some(l => l.includes(k))) ||
           ACTION_KEYS.some(k => lower.some(l => l.includes(k)));
}

function extractOIA(data: unknown): OIAInsight[] {
    if (Array.isArray(data)) {
        const results: OIAInsight[] = [];
        for (const item of data) {
            results.push(...extractOIA(item));
        }
        return results;
    }

    if (typeof data === 'object' && data !== null) {
        const obj = data as Record<string, unknown>;
        const keys = Object.keys(obj);

        if (isOIALike(keys)) {
            const observation = fuzzyGet(obj, OBSERVATION_KEYS);
            const insight = fuzzyGet(obj, INSIGHT_KEYS);
            const action = fuzzyGet(obj, ACTION_KEYS);

            // Only accept if at least observation or insight is non-empty
            if (observation || insight) {
                return [{
                    observation: observation || 'Data pattern detected in the uploaded dataset.',
                    insight: insight || 'This pattern may impact downstream analysis and model training accuracy.',
                    action: action || 'Review the anomalies in the Detection tab and proceed to Cleaning for remediation.',
                }];
            }
        }

        // Recurse into values
        const results: OIAInsight[] = [];
        for (const val of Object.values(obj)) {
            results.push(...extractOIA(val));
        }
        return results;
    }

    return [];
}

export default function Insights({ sessionId, cachedInsights, onInsightsLoaded }: InsightsProps) {
    const hasCachedData = cachedInsights && cachedInsights.length > 0;
    const [insights, setInsights] = useState<OIAInsight[]>(hasCachedData ? cachedInsights : []);
    const [loading, setLoading] = useState(!hasCachedData);
    const [error, setError] = useState<string | null>(null);

    const fetchInsights = () => {
        setLoading(true);
        setError(null);
        setInsights([]);

        axios.get(`http://127.0.0.1:8000/api/insights/${sessionId}`)
            .then((res) => {
                const rawData = res.data?.insights ?? res.data;
                const finalArray = extractOIA(rawData);
                console.log('[DataSentinel] Insights received:', finalArray.length, 'items', finalArray);
                setInsights(finalArray);
                setLoading(false);
                // Cache in parent so tab switches don't re-fetch
                if (onInsightsLoaded && finalArray.length > 0) {
                    onInsightsLoaded(finalArray);
                }
            })
            .catch((err) => {
                console.error('[DataSentinel] Insights error:', err);
                setError(err.response?.data?.detail || "Failed to generate AI insights.");
                setLoading(false);
            });
    };

    useEffect(() => {
        // Only fetch if we don't already have cached data
        if (!hasCachedData) {
            fetchInsights();
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-neutral-400 bg-neutral-900/50 border border-neutral-800 rounded-2xl">
                <div className="relative mb-6">
                    <div className="absolute inset-0 bg-purple-500 blur-xl opacity-20 rounded-full animate-pulse"></div>
                    <Brain className="w-12 h-12 text-purple-500 relative z-10 animate-bounce" />
                </div>
                <p className="text-lg font-medium text-white mb-2">Consulting the AI...</p>
                <p className="text-sm">Analyzing data topology and generating OIA framework.</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-500/10 border border-red-500/20 p-6 rounded-2xl flex items-start">
                <AlertTriangle className="w-6 h-6 text-red-500 mr-4 shrink-0" />
                <div>
                    <h3 className="text-red-500 font-bold mb-1">Analysis Failed</h3>
                    <p className="text-red-400/80 text-sm">{error}</p>
                </div>
            </div>
        );
    }

    // --- EMPTY STATE HANDLER ---
    if (!loading && insights.length === 0 && !error) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-neutral-500 bg-neutral-900/30 rounded-2xl border border-neutral-800 border-dashed">
                <Brain className="w-10 h-10 mb-4 opacity-20" />
                <h3 className="text-lg font-bold text-white mb-1">No Insights Generated</h3>
                <p className="text-sm mb-4 max-w-md text-center">The AI model returned an unreadable format, or Ollama may not be running. Please try again.</p>
                <button
                    onClick={fetchInsights}
                    className="px-5 py-2.5 bg-white text-black font-bold rounded-xl hover:bg-neutral-200 transition-colors text-sm"
                >
                    Retry Analysis
                </button>
            </div>
        );
    }

    return (
        <div className="w-full space-y-6">
            <div className="grid grid-cols-1 gap-6">
                {insights.map((item, idx) => (
                    <motion.div
                        key={idx}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: idx * 0.15 }}
                        className="bg-neutral-900 border border-neutral-800 rounded-2xl overflow-hidden flex flex-col md:flex-row"
                    >
                        {/* 1. Observation (Neutral) */}
                        <div className="flex-1 p-6 md:border-r border-neutral-800 bg-black/20">
                            <div className="flex items-center text-neutral-500 mb-3">
                                <Eye className="w-4 h-4 mr-2" />
                                <span className="text-xs font-bold uppercase tracking-wider">Observation</span>
                            </div>
                            <p className="text-neutral-300 leading-relaxed text-sm">
                                {item.observation}
                            </p>
                        </div>

                        {/* 2. Insight (Purple tint) */}
                        <div className="flex-1 p-6 md:border-r border-neutral-800 bg-purple-900/5 relative overflow-hidden">
                            <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-3xl -mr-16 -mt-16"></div>
                            <div className="flex items-center text-purple-400 mb-3 relative z-10">
                                <Brain className="w-4 h-4 mr-2" />
                                <span className="text-xs font-bold uppercase tracking-wider">Insight</span>
                            </div>
                            <p className="text-white font-medium leading-relaxed text-sm relative z-10">
                                {item.insight}
                            </p>
                        </div>

                        {/* 3. Action (Green tint) */}
                        <div className="flex-1 p-6 bg-emerald-900/5 relative overflow-hidden">
                            <div className="absolute bottom-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl -mr-16 -mb-16"></div>
                            <div className="flex items-center text-emerald-400 mb-3 relative z-10">
                                <Zap className="w-4 h-4 mr-2" />
                                <span className="text-xs font-bold uppercase tracking-wider">Recommended Action</span>
                            </div>
                            <p className="text-emerald-50 leading-relaxed text-sm relative z-10">
                                {item.action}
                            </p>
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}