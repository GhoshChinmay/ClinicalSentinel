"use client";

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { API_BASE } from '@/lib/api';
import type { AnomalyRow, QuarantineResponse, CleanResponse } from '@/types/api';
import { motion, AnimatePresence } from 'framer-motion';
import { Trash2, Scissors, CheckCircle, Loader2, Shield, EyeOff, Activity, X, AlertTriangle, Download, Info, Sparkles } from 'lucide-react';

// --- THE QUARANTINE VAULT MODAL (Unchanged) ---
function QuarantineVaultModal({ sessionId, onClose }: { sessionId: string, onClose: () => void }) {
    const [auditData, setAuditData] = useState<AnomalyRow[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchVault = async () => {
            try {
                const res = await api.get<QuarantineResponse>(`/api/quarantine/${sessionId}`);
                setAuditData(res.data.data || []);
            } catch (err) {
                console.error("Failed to fetch quarantine vault");
            } finally {
                setLoading(false);
            }
        };
        fetchVault();
    }, [sessionId]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-[#0A0A0A] border border-neutral-800 rounded-2xl shadow-2xl w-full max-w-6xl max-h-[85vh] flex flex-col overflow-hidden"
            >
                <div className="flex items-center justify-between p-6 border-b border-neutral-800 bg-[#050505]">
                    <div className="flex items-center">
                        <Shield className="w-6 h-6 text-blue-400 mr-3" />
                        <div>
                            <h2 className="text-xl font-bold text-white">Quarantine Vault Audit Log</h2>
                            <p className="text-xs text-neutral-500">Viewing isolated anomalies removed from the main pipeline.</p>
                        </div>
                    </div>
                    <div className="flex items-center space-x-4">
                        <button
                            onClick={() => {
                                const headers = Object.keys(auditData[0] || {}).join(',');
                                const rows = auditData.map(row => Object.values(row).join(','));
                                const csv = [headers, ...rows].join('\n');
                                const blob = new Blob([csv], { type: 'text/csv' });
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url;
                                a.download = 'quarantine_audit.csv';
                                a.click();
                                URL.revokeObjectURL(url);
                            }}
                            disabled={auditData.length === 0}
                            className="flex items-center text-xs font-bold text-neutral-300 hover:text-white bg-neutral-800 hover:bg-neutral-700 px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                        >
                            <Download className="w-4 h-4 mr-2" />
                            Export Audit CSV
                        </button>
                        <button onClick={onClose} className="p-2 text-neutral-500 hover:text-white transition-colors">
                            <X className="w-6 h-6" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-auto p-0">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center h-64">
                            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
                            <p className="text-neutral-400 font-medium">Decrypting Vault Records...</p>
                        </div>
                    ) : auditData.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-neutral-500">
                            <CheckCircle className="w-12 h-12 mb-2 opacity-50" />
                            <p>Vault is empty. No anomalies quarantined.</p>
                        </div>
                    ) : (
                        <table className="w-full text-left border-collapse">
                            <thead className="bg-[#111] sticky top-0 z-10 border-b border-neutral-800">
                                <tr>
                                    <th className="p-4 text-xs font-bold text-neutral-400 uppercase tracking-wider">Threat Level</th>
                                    <th className="p-4 text-xs font-bold text-neutral-400 uppercase tracking-wider w-1/3">AI Justification</th>
                                    <th className="p-4 text-xs font-bold text-neutral-400 uppercase tracking-wider">Raw Data Fragment</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-neutral-800/50">
                                {auditData.map((row, i) => (
                                    <tr key={i} className="hover:bg-neutral-900/50 transition-colors">
                                        <td className="p-4">
                                            <div className="flex items-center">
                                                <AlertTriangle className={`w-4 h-4 mr-2 ${row.Threat_Score > 80 ? 'text-red-500' : 'text-yellow-500'}`} />
                                                <span className={`font-bold ${row.Threat_Score > 80 ? 'text-red-400' : 'text-yellow-400'}`}>
                                                    {row.Threat_Score}%
                                                </span>
                                            </div>
                                        </td>
                                        <td className="p-4 text-sm text-neutral-300 leading-relaxed border-l border-neutral-800/50 bg-[#111111]/30">
                                            {row.AI_Reason || "Complex mathematical anomaly detected."}
                                        </td>
                                        <td className="p-4 text-xs text-neutral-500 font-mono overflow-hidden">
                                            {JSON.stringify(
                                                Object.fromEntries(Object.entries(row).filter(([k]) => !['is_anomaly', 'AI_Reason', 'Threat_Score'].includes(k)).slice(0, 3))
                                            ).substring(0, 60)}...
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </motion.div>
        </div>
    );
}

// --- MAIN CLEAN TAB COMPONENT ---
interface CleanProps {
    sessionId: string;
    onComplete: () => void;
    recommendedMethod?: string;
    cleaningRationale?: string;
}

export default function Clean({ sessionId, onComplete, recommendedMethod = 'quarantine', cleaningRationale }: CleanProps) {
    const [loadingAction, setLoadingAction] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const [showVault, setShowVault] = useState(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    // Upgraded array with Analogies and Plain English Explanations
    const cleaningMethods = [
        {
            id: 'quarantine', icon: Shield, title: 'Quarantine Protocol',
            techDesc: 'Moves anomalies to a secure audit file. Leaves main dataset perfectly clean.',
            analogy: 'The Evidence Room',
            simpleDesc: 'Safely removes the bad data from your main dashboard and locks it in a secure Vault so you can review it later.',
            color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30', btnHover: 'hover:bg-blue-600'
        },
        {
            id: 'winsorize', icon: Scissors, title: 'Smart Winsorization',
            techDesc: 'Caps extreme numerical outliers to the 95th percentile. Prevents data loss.',
            analogy: 'The Speed Limit',
            simpleDesc: 'Keeps the data row, but takes crazy, impossible numbers (like a $10,000 toothbrush) and caps them at a normal, realistic maximum.',
            color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/30', btnHover: 'hover:bg-purple-600'
        },
        {
            id: 'mask', icon: EyeOff, title: 'Categorical Masking',
            techDesc: 'Overwrites malicious or anomalous text strings with [REDACTED] tags.',
            analogy: 'The Censor\'s Marker',
            simpleDesc: 'Protects your database by crossing out malicious text or fake bot names with a [REDACTED] tag, while keeping the rest of the transaction perfectly intact.',
            color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', btnHover: 'hover:bg-yellow-600'
        },
        {
            id: 'impute', icon: Activity, title: 'Contextual Imputation',
            techDesc: 'Uses Predictive KNN to fill in corrupted cells based on the user\'s past behavior.',
            analogy: 'The Auto-Correct',
            simpleDesc: 'Acts like smart auto-correct. If a sensor glitches and drops a number, the AI looks at the surrounding normal data and fills in the blank with a highly educated guess.',
            color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', btnHover: 'hover:bg-emerald-600'
        },
        {
            id: 'drop', icon: Trash2, title: 'Hard Drop',
            techDesc: 'Permanently deletes anomalous rows. Destructive but ensures strict data integrity.',
            analogy: 'The Bouncer',
            simpleDesc: 'Permanently deletes the corrupted row from existence. Only use this if you are 100% sure the data is useless junk.',
            color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', btnHover: 'hover:bg-red-600'
        },
    ];

    const handleClean = async (action: string) => {
        setLoadingAction(action);
        setErrorMsg(null);
        try {
            const res = await api.post<CleanResponse>(`/api/clean/${sessionId}?action=${action}`);
            setSuccessMsg(`Successfully applied ${action}. Final dataset has ${res.data.new_total} rows.`);
        } catch (err: unknown) {
            const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
            const detail = axiosErr.response?.data?.detail || axiosErr.message || "An unknown error occurred during cleaning.";
            console.error("DataSentinel: Clean failed —", detail);
            setErrorMsg(`Cleaning failed: ${detail}`);
        } finally {
            setLoadingAction(null);
        }
    };

    return (
        <div className="w-full mt-6">
            {successMsg ? (
                <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="p-12 text-center flex flex-col items-center justify-center bg-green-500/10 border border-green-500/20 rounded-2xl">
                    <CheckCircle className="w-16 h-16 text-green-400 mb-4" />
                    <h3 className="text-2xl font-semibold text-white mb-2">Sanitization Complete</h3>
                    <p className="text-green-400/80 mb-8">{successMsg}</p>

                    <div className="flex space-x-4">
                        <button onClick={() => setShowVault(true)} className="px-6 py-3 bg-neutral-800 hover:bg-neutral-700 text-white font-bold rounded-xl transition-colors border border-neutral-700 flex items-center">
                            <Shield className="w-5 h-5 mr-2 text-blue-400" />
                            Open Quarantine Vault
                        </button>
                        <button onClick={onComplete} className="px-6 py-3 bg-green-600 hover:bg-green-500 text-white font-bold rounded-xl transition-colors flex items-center">
                            Continue to Export →
                        </button>
                    </div>
                </motion.div>
            ) : (
                <>
                    {/* --- NEW: AI RECOMMENDATION BANNER --- */}
                    {cleaningRationale && (
                        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-8 p-6 bg-blue-500/10 border border-blue-500/30 rounded-2xl flex items-start shadow-[0_0_30px_rgba(59,130,246,0.1)]">
                            <Sparkles className="w-8 h-8 text-blue-400 mr-4 shrink-0 mt-1" />
                            <div>
                                <h3 className="text-lg font-bold text-white mb-1">
                                    AI Recommended Action: {recommendedMethod.charAt(0).toUpperCase() + recommendedMethod.slice(1)}
                                </h3>
                                <p className="text-blue-200 text-sm leading-relaxed">{cleaningRationale}</p>
                            </div>
                        </motion.div>
                    )}

                    {/* --- ERROR BANNER --- */}
                    {errorMsg && (
                        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 p-5 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-start">
                            <AlertTriangle className="w-6 h-6 text-red-400 mr-3 shrink-0 mt-0.5" />
                            <div className="flex-1">
                                <h3 className="text-sm font-bold text-red-400 mb-1">Operation Failed</h3>
                                <p className="text-red-300/80 text-sm leading-relaxed">{errorMsg}</p>
                            </div>
                            <button onClick={() => setErrorMsg(null)} className="p-1 text-red-400 hover:text-white transition-colors ml-4">
                                <X className="w-4 h-4" />
                            </button>
                        </motion.div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 perspective-[1000px]">
                        {cleaningMethods.map((method) => {
                            const Icon = method.icon;
                            // Dynamically match the backend's recommendation to the card ID
                            const isRecommended = method.id === recommendedMethod;

                            return (
                                <div key={method.id} className="group relative w-full h-[280px] [perspective:1000px]">
                                    {/* 3D Flip Container */}
                                    <div className="w-full h-full transition-transform duration-700 [transform-style:preserve-3d] group-hover:[transform:rotateY(180deg)]">

                                        {/* --- FRONT OF CARD (Tech View) --- */}
                                        <div className={`absolute inset-0 [backface-visibility:hidden] bg-neutral-900 border ${isRecommended ? 'border-blue-500/50 shadow-[0_0_20px_rgba(59,130,246,0.2)]' : 'border-neutral-800'} p-8 rounded-2xl flex flex-col`}>
                                            {isRecommended && (
                                                <div className="absolute top-0 right-0 bg-blue-500 text-white text-xs font-bold px-4 py-1.5 rounded-bl-lg rounded-tr-xl uppercase tracking-wider z-10 shadow-lg">
                                                    AI Pick
                                                </div>
                                            )}

                                            <div className="flex items-center justify-between mb-6">
                                                <div className={`w-12 h-12 ${method.bg} rounded-xl flex items-center justify-center`}>
                                                    <Icon className={`w-6 h-6 ${method.color}`} />
                                                </div>
                                                <div className="flex items-center text-neutral-500 text-xs">
                                                    <Info className="w-4 h-4 mr-1" /> Hover to learn
                                                </div>
                                            </div>

                                            <h3 className="text-xl font-semibold mb-2">{method.title}</h3>
                                            <p className="text-neutral-400 text-sm flex-1">{method.techDesc}</p>
                                        </div>

                                        {/* --- BACK OF CARD (Plain English / Action View) --- */}
                                        <div className={`absolute inset-0 [backface-visibility:hidden] [transform:rotateY(180deg)] bg-neutral-800 border ${method.border} p-8 rounded-2xl flex flex-col justify-between`}>

                                            <div>
                                                <div className="flex items-center mb-3">
                                                    <Icon className={`w-5 h-5 mr-2 ${method.color}`} />
                                                    <h3 className={`text-lg font-bold ${method.color}`}>&quot;{method.analogy}&quot;</h3>
                                                </div>
                                                <p className="text-white text-sm leading-relaxed">{method.simpleDesc}</p>
                                            </div>

                                            <button
                                                onClick={() => handleClean(method.id)}
                                                disabled={!!loadingAction}
                                                className={`w-full py-3 mt-4 text-white font-bold rounded-lg transition-colors flex justify-center items-center shadow-lg ${isRecommended ? 'bg-blue-600 hover:bg-blue-500' : `bg-neutral-900 ${method.btnHover}`}`}
                                            >
                                                {loadingAction === method.id ? (
                                                    <Loader2 className="w-5 h-5 animate-spin" />
                                                ) : (
                                                    `Apply ${method.id.charAt(0).toUpperCase() + method.id.slice(1)}`
                                                )}
                                            </button>

                                        </div>

                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </>
            )}

            <AnimatePresence>
                {showVault && <QuarantineVaultModal sessionId={sessionId} onClose={() => setShowVault(false)} />}
            </AnimatePresence>
        </div>
    );
}