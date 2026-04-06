import { useState, useEffect } from 'react';
import api from '@/lib/api';
import type { AnomalyRow, SessionDataResponse } from '@/types/api';
import { motion } from 'framer-motion';
import { ShieldAlert, CheckCircle, FileWarning, AlertTriangle, AlertCircle, Crosshair, Activity, ThumbsUp, ThumbsDown } from 'lucide-react';

export default function Detection({ sessionId }: { sessionId: string }) {
    const [data, setData] = useState<AnomalyRow[]>([]);
    const [totalAnomalies, setTotalAnomalies] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // NEW: Slider State
    const [threshold, setThreshold] = useState<number>(0);

    // NEW: Feedback State
    const [feedbackMap, setFeedbackMap] = useState<Record<number, 'correct' | 'incorrect'>>({});

    const handleFeedback = async (row: AnomalyRow, idx: number, isCorrect: boolean) => {
        try {
            await api.post('/api/feedback/', {
                session_id: sessionId,
                row_data: row,
                is_correct: isCorrect
            });
            setFeedbackMap(prev => ({ ...prev, [idx]: isCorrect ? 'correct' : 'incorrect' }));
        } catch (e) {
            console.error("Failed to submit feedback", e);
        }
    };

    useEffect(() => {
        if (!sessionId) {
            setError("Critical Error: Session ID is missing. The upload likely failed. Please refresh and try uploading again.");
            setLoading(false);
            return;
        }

        const fetchData = async () => {
            try {
                const res = await api.get<SessionDataResponse>(`/api/data/${sessionId}?is_cleaned=false&only_anomalies=true`);

                if (res.data && Array.isArray(res.data.data)) {
                    setData(res.data.data);
                    setTotalAnomalies(res.data.total_anomalies || 0);
                } else {
                    throw new Error("Invalid data format received from the server.");
                }
            } catch (err: unknown) {
                console.error("Failed to load anomalies", err);
                const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
                setError(axiosErr.response?.data?.detail || axiosErr.message || "Failed to load anomaly report.");
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [sessionId]);

    if (loading) return (
        <div className="w-full mt-6 flex flex-col items-center justify-center h-64 border border-neutral-800 rounded-2xl bg-[#0A0A0A]">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <span className="text-neutral-500 font-medium">Processing large dataset payload...</span>
        </div>
    );

    if (error) return (
        <div className="w-full mt-6 bg-red-500/10 border border-red-900/50 p-6 rounded-2xl flex items-start text-red-400">
            <AlertCircle className="w-6 h-6 mr-3 shrink-0" />
            <div>
                <h3 className="font-bold text-lg mb-1">Detection Engine Failed</h3>
                <p className="text-sm">{error}</p>
            </div>
        </div>
    );

    // NEW: Filter the data dynamically based on the slider
    const displayData = data.filter(row => {
        if (row.Threat_Score === undefined || row.Threat_Score === null) return true;
        return row.Threat_Score >= threshold;
    }).slice(0, 100);

    // Check if the dataset is capable of Threat Scoring (has ML output > 0)
    const hasThreatScores = data.length > 0 && data.some(r => r.Threat_Score && r.Threat_Score > 0);

    return (
        <div className="w-full mt-6">
            <div className="flex items-center justify-between bg-neutral-900 border border-neutral-800 p-6 rounded-2xl mb-6">
                <div>
                    <h3 className="text-xl font-semibold flex items-center"><ShieldAlert className="w-5 h-5 text-red-400 mr-2" /> Scan Complete</h3>
                    <p className="text-sm text-neutral-400">Our Multi-Modal AI scanned numbers, text, and categories for errors.</p>
                </div>
                <div className="text-right">
                    <p className="text-3xl font-bold text-red-400">{totalAnomalies}</p>
                    <p className="text-xs text-neutral-500 uppercase font-bold tracking-wider">Anomalies Found</p>
                </div>
            </div>

            {/* NEW: The Precision / Recall Slider UI */}
            {hasThreatScores && (
                <div className="mb-6 p-6 bg-[#0A0A0A] border border-neutral-800 rounded-2xl shadow-xl">
                    <div className="flex justify-between items-center mb-4">
                        <div>
                            <h4 className="font-bold text-white flex items-center">
                                <Crosshair className="w-4 h-4 mr-2 text-blue-500" />
                                Threat Score Strictness
                            </h4>
                            <p className="text-xs text-neutral-400 mt-1">Filter the visible anomalies based on the Supervised Classifier&apos;s confidence score.</p>
                        </div>
                        <div className="text-right">
                            <span className="text-2xl font-black text-blue-500">{threshold}%</span>
                            <span className="text-[10px] text-neutral-500 block uppercase tracking-widest mt-1">Threshold</span>
                        </div>
                    </div>

                    <input
                        type="range"
                        min="0"
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

            {totalAnomalies > 100 && (
                <div className="mb-4 flex items-center p-3 bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 text-xs rounded-lg">
                    <AlertTriangle className="w-4 h-4 mr-2 shrink-0" />
                    <span>Displaying the top 100 anomalies to maintain browser performance. All {totalAnomalies} will be handled during the Smart Cleaning step.</span>
                </div>
            )}

            <div className="bg-[#0A0A0A] border border-neutral-800 rounded-2xl overflow-hidden">
                {displayData.length > 0 ? (
                    <div className="overflow-x-auto max-h-[500px]">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-neutral-900 text-neutral-500 sticky top-0 uppercase text-xs font-semibold z-10">
                                <tr>
                                    <th className="px-6 py-4">Row Data</th>
                                    <th className="px-6 py-4">AI Explanation</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-neutral-800">
                                {displayData.map((row, idx) => {
                                    const { is_anomaly: _a, AI_Reason: _b, Threat_Score: _c, SHAP_Payload: _d, ...rowData } = row;

                                    let shapData: Array<{ feature: string; impact: number }> | null = null;
                                    try {
                                        if (row.SHAP_Payload) {
                                            shapData = JSON.parse(row.SHAP_Payload);
                                        }
                                    } catch (e) {
                                        // Ignore parse error
                                    }

                                    return (
                                        <motion.tr initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: idx * 0.02 }} key={idx} className="hover:bg-neutral-900/50">

                                            {/* THE NEW STRUCTURED GRID FIX */}
                                            <td className="px-6 py-4 w-1/2 align-top">
                                                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-40 overflow-y-auto pr-2 custom-scrollbar">
                                                    {Object.entries(rowData).map(([key, val]) => (
                                                        <div key={key} className="flex flex-col bg-black/40 p-2 rounded-lg border border-neutral-800/60">
                                                            <span className="text-[9px] text-neutral-500 uppercase font-bold tracking-wider mb-0.5">{key}</span>
                                                            <span className="text-xs font-mono text-neutral-300 truncate" title={String(val)}>
                                                                {/* Format long decimals so they don't break the UI */}
                                                                {typeof val === 'number' && Number.isFinite(val) && !Number.isInteger(val) ? val.toFixed(4) : String(val ?? '—')}
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </td>

                                            <td className="px-6 py-4 w-1/2 align-top">
                                                <div className="flex flex-col space-y-2">
                                                    <div className="flex items-start text-yellow-500/90 bg-yellow-500/10 p-3 rounded-lg border border-yellow-500/20">
                                                        <FileWarning className="w-4 h-4 mr-2 mt-0.5 shrink-0" />
                                                        <span>{row.AI_Reason || "Flagged as an anomaly by the detection model."}</span>
                                                    </div>

                                                    {row.Threat_Score !== undefined && row.Threat_Score > 0 && (
                                                        <div className="inline-flex items-center w-fit text-xs font-bold px-2.5 py-1 rounded-md border border-blue-900/50 bg-blue-500/10 text-blue-400">
                                                            Threat Score: {row.Threat_Score}%
                                                        </div>
                                                    )}

                                                    {/* NEW: SHAP Feature Attribution Panel */}
                                                    {shapData && shapData.length > 0 && (
                                                        <div className="mt-2 bg-black/40 border border-neutral-800/60 rounded-lg p-3">
                                                            <h5 className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider mb-2 flex items-center">
                                                                <Activity className="w-3 h-3 mr-1 text-purple-400" />
                                                                SHAP Feature Attribution
                                                            </h5>
                                                            <div className="space-y-2">
                                                                {shapData.map((shap, sIdx) => {
                                                                    const isPositive = shap.impact > 0;
                                                                    // Normalize width for basic UI display (limit to between 5% and 100%)
                                                                    const width = Math.min(Math.max(Math.abs(shap.impact) * 100, 5), 100);
                                                                    return (
                                                                        <div key={sIdx} className="flex flex-col">
                                                                            <div className="flex justify-between text-xs mb-1">
                                                                                <span className="text-neutral-300 font-mono">{shap.feature}</span>
                                                                                <span className={`font-mono ${isPositive ? 'text-red-400' : 'text-blue-400'}`}>
                                                                                    {isPositive ? '+' : ''}{shap.impact.toFixed(3)}
                                                                                </span>
                                                                            </div>
                                                                            <div className="w-full bg-neutral-900 rounded-full h-1.5 overflow-hidden flex">
                                                                                <div 
                                                                                    className={`h-full rounded-full ${isPositive ? 'bg-red-500/80' : 'bg-blue-500/80'}`}
                                                                                    style={{ width: `${width}%` }} 
                                                                                />
                                                                            </div>
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Active Learning Feedback Buttons */}
                                                    <div className="mt-4 flex items-center space-x-2 border-t border-neutral-800/60 pt-3">
                                                        <span className="text-[10px] uppercase font-bold text-neutral-500 mr-2">Was this correct?</span>
                                                        <button 
                                                            onClick={() => handleFeedback(row, idx, true)}
                                                            disabled={feedbackMap[idx] !== undefined}
                                                            className={`flex items-center px-2 py-1 space-x-1 rounded text-[10px] font-bold border transition-colors ${feedbackMap[idx] === 'correct' ? 'bg-green-500/20 text-green-400 border-green-500/50' : feedbackMap[idx] === 'incorrect' ? 'opacity-50 cursor-not-allowed bg-black text-neutral-600 border-neutral-800' : 'bg-black text-neutral-400 border-neutral-800 hover:text-green-400 hover:border-green-500/50'}`}
                                                        >
                                                            <ThumbsUp className="w-3 h-3" />
                                                            <span>Yes</span>
                                                        </button>
                                                        <button 
                                                            onClick={() => handleFeedback(row, idx, false)}
                                                            disabled={feedbackMap[idx] !== undefined}
                                                            className={`flex items-center px-2 py-1 space-x-1 rounded text-[10px] font-bold border transition-colors ${feedbackMap[idx] === 'incorrect' ? 'bg-red-500/20 text-red-400 border-red-500/50' : feedbackMap[idx] === 'correct' ? 'opacity-50 cursor-not-allowed bg-black text-neutral-600 border-neutral-800' : 'bg-black text-neutral-400 border-neutral-800 hover:text-red-400 hover:border-red-500/50'}`}
                                                        >
                                                            <ThumbsDown className="w-3 h-3" />
                                                            <span>No</span>
                                                        </button>
                                                    </div>

                                                </div>
                                            </td>
                                        </motion.tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="p-12 text-center flex flex-col items-center justify-center text-neutral-500">
                        <CheckCircle className="w-12 h-12 mb-4 opacity-30" />
                        <h3 className="text-lg font-medium text-neutral-400">No anomalies match this strictness</h3>
                        <p className="text-sm mt-1">Lower the Threat Score threshold to view more rows.</p>
                    </div>
                )}
            </div>
        </div>
    );
}