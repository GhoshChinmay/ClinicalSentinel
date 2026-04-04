import { useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Trash2, Scissors, CheckCircle, Loader2 } from 'lucide-react';

export default function Clean({ sessionId, onComplete }: { sessionId: string, onComplete: () => void }) {
    const [loadingAction, setLoadingAction] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);

    const handleClean = async (action: 'drop' | 'cap') => {
        setLoadingAction(action);
        try {
            const res = await axios.post(`http://127.0.0.1:8000/api/clean/${sessionId}`, { action });
            setSuccessMsg(action === 'drop' ? `Removed ${res.data.rows_removed} corrupted rows.` : `Capped extreme outliers. 0 rows lost.`);
            setTimeout(() => {
                onComplete(); // Automatically move them to the next tab after 1.5 seconds
            }, 1500);
        } catch (err) {
            console.error("Failed to clean");
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
                    <p className="text-green-400/80">{successMsg}</p>
                    <p className="text-neutral-500 text-sm mt-4 animate-pulse">Moving to Review & Edit...</p>
                </motion.div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                    {/* Option 1: Drop */}
                    <div className="bg-neutral-900 border border-neutral-800 p-8 rounded-2xl relative overflow-hidden group hover:border-red-500/30 transition-colors">
                        <div className="absolute top-0 right-0 bg-red-500/10 text-red-400 text-xs font-bold px-3 py-1 rounded-bl-lg uppercase tracking-wider">Recommended</div>
                        <div className="w-12 h-12 bg-red-500/10 rounded-xl flex items-center justify-center mb-6">
                            <Trash2 className="w-6 h-6 text-red-400" />
                        </div>
                        <h3 className="text-xl font-semibold mb-2">Aggressive Drop</h3>
                        <p className="text-neutral-400 text-sm mb-8 h-10">Completely deletes rows flagged as highly anomalous. Ensures strict data integrity.</p>
                        <button
                            onClick={() => handleClean('drop')} disabled={!!loadingAction}
                            className="w-full py-3 bg-white text-black font-medium rounded-lg hover:bg-neutral-200 transition-colors flex justify-center items-center"
                        >
                            {loadingAction === 'drop' ? <Loader2 className="w-5 h-5 animate-spin" /> : "Apply Drop"}
                        </button>
                    </div>

                    {/* Option 2: Cap */}
                    <div className="bg-neutral-900 border border-neutral-800 p-8 rounded-2xl hover:border-blue-500/30 transition-colors">
                        <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mb-6">
                            <Scissors className="w-6 h-6 text-blue-400" />
                        </div>
                        <h3 className="text-xl font-semibold mb-2">Smooth Extremes (Cap)</h3>
                        <p className="text-neutral-400 text-sm mb-8 h-10">Keeps every row, but compresses wild numbers down to normal percentiles. Best for small datasets.</p>
                        <button
                            onClick={() => handleClean('cap')} disabled={!!loadingAction}
                            className="w-full py-3 bg-neutral-800 text-white font-medium rounded-lg hover:bg-neutral-700 transition-colors flex justify-center items-center"
                        >
                            {loadingAction === 'cap' ? <Loader2 className="w-5 h-5 animate-spin" /> : "Apply Capping"}
                        </button>
                    </div>

                </div>
            )}
        </div>
    );
}