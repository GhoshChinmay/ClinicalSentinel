import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ComposedChart, Scatter, Line, CartesianGrid } from 'recharts';
import { Activity, ShieldCheck, Zap, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function Visualizer({ sessionId }: { sessionId: string }) {
    const [data, setData] = useState<any>(null);
    const [activeTab, setActiveTab] = useState<'before' | 'after' | 'correlation'>('before');
    const [corrX, setCorrX] = useState('');
    const [corrY, setCorrY] = useState('');

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!sessionId) return;

        const fetchViz = async () => {
            try {
                setLoading(true);
                setError(null);

                // We fetch with is_cleaned=true to ensure we get the latest processed data
                const res = await axios.get(`http://127.0.0.1:8000/api/viz/${sessionId}?is_cleaned=true`);
                setData(res.data);

                if (res.data.columns && res.data.columns.length >= 2) {
                    setCorrX(res.data.columns[0]);
                    setCorrY(res.data.columns[1]);
                }
            } catch (err: any) {
                console.error("Visualizer fetch error:", err);
                setError(err.response?.data?.detail || "Fatal Server Error. Check Python Terminal.");
            } finally {
                setLoading(false);
            }
        };

        fetchViz();
    }, [sessionId]);

    const correlationData = useMemo(() => {
        if (!data || !corrX || !corrY || !data.clean_sample) return { points: [], status: 'No Data', r: 0 };

        const validData = data.clean_sample.filter((d: any) => d[corrX] != null && d[corrY] != null);
        const n = validData.length;
        if (n < 2) return { points: [], status: 'Insufficient Data', r: 0 };

        let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
        validData.forEach((d: any) => {
            const x = d[corrX];
            const y = d[corrY];
            sumX += x; sumY += y;
            sumXY += x * y;
            sumX2 += x * x; sumY2 += y * y;
        });

        const num = (n * sumXY - sumX * sumY);
        const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
        const r = den === 0 ? 0 : num / den;

        // DYNAMIC STATUS LABELS: Adjusted for high-dimensional/PCA datasets
        let status = 'Neutral / No Correlation';
        const absR = Math.abs(r);
        if (absR > 0.05 && absR <= 0.2) status = r > 0 ? 'Very Weak Positive' : 'Very Weak Negative';
        if (absR > 0.2 && absR <= 0.4) status = r > 0 ? 'Weak Positive' : 'Weak Negative';
        if (absR > 0.4 && absR <= 0.7) status = r > 0 ? 'Moderate Positive' : 'Moderate Negative';
        if (absR > 0.7) status = r > 0 ? 'Strong Positive' : 'Strong Negative';

        const m = (n * sumX2 - sumX * sumX) === 0 ? 0 : (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        const b = (sumY - m * sumX) / n;

        const points = validData.map((d: any) => ({
            ...d,
            trendLine: m * d[corrX] + b
        })).sort((a: any, b: any) => a[corrX] - b[corrX]);

        return { points, status, r: r.toFixed(3) };
    }, [data, corrX, corrY]);

    if (loading) return (
        <div className="w-full mt-6 flex flex-col items-center justify-center h-64 border border-neutral-800 rounded-2xl bg-[#0A0A0A]">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <span className="text-neutral-500 font-medium">Crunching dataset millions...</span>
        </div>
    );

    if (error) return (
        <div className="w-full mt-6 bg-red-500/10 border border-red-900/50 p-6 rounded-2xl flex items-start text-red-400">
            <AlertCircle className="w-6 h-6 mr-3 shrink-0" />
            <div>
                <h3 className="font-bold text-lg mb-1">Visualizer Engine Failed</h3>
                <p className="text-sm">{error}</p>
            </div>
        </div>
    );

    if (!data) return null;

    return (
        <div className="w-full mt-6 bg-[#0A0A0A] border border-neutral-800 rounded-2xl overflow-hidden">
            <div className="flex flex-col md:flex-row md:items-center justify-between p-4 border-b border-neutral-800 bg-neutral-900/30 gap-4">
                <div className="flex space-x-2">
                    <button onClick={() => setActiveTab('before')} className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium ${activeTab === 'before' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'text-neutral-400 hover:bg-neutral-800'}`}>
                        <Activity className="w-4 h-4 mr-2" /> Dataset Distribution (Before)
                    </button>
                    <button onClick={() => setActiveTab('after')} className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium ${activeTab === 'after' ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'text-neutral-400 hover:bg-neutral-800'}`}>
                        <ShieldCheck className="w-4 h-4 mr-2" /> Dataset Distribution (After)
                    </button>
                    <button onClick={() => setActiveTab('correlation')} className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium ${activeTab === 'correlation' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'text-neutral-400 hover:bg-neutral-800'}`}>
                        <Zap className="w-4 h-4 mr-2" /> Variable Correlation
                    </button>
                </div>

                {activeTab === 'correlation' && (
                    <div className="flex items-center space-x-3 bg-neutral-900 p-2 rounded-xl border border-neutral-800">
                        <span className="text-xs text-neutral-500 ml-2">X:</span>
                        <select value={corrX} onChange={e => setCorrX(e.target.value)} className="bg-[#0A0A0A] text-white text-xs p-1 outline-none border border-neutral-700 rounded">
                            {data.columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <span className="text-xs text-neutral-500">Y:</span>
                        <select value={corrY} onChange={e => setCorrY(e.target.value)} className="bg-[#0A0A0A] text-white text-xs p-1 outline-none border border-neutral-700 rounded">
                            {data.columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                )}
            </div>

            <div className="p-6 h-[450px]">
                <AnimatePresence mode="wait">
                    {activeTab === 'before' && (
                        <motion.div key="before" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full w-full">
                            <h3 className="text-sm font-semibold text-red-400 mb-4">Whole Dataset Integrity (Uncleaned)</h3>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={data.global_raw_hist} margin={{ bottom: 20 }}>
                                    <XAxis dataKey="bin" stroke="#525252" fontSize={10} angle={-45} textAnchor="end" />
                                    <YAxis hide />
                                    <Tooltip contentStyle={{ backgroundColor: '#171717', border: 'none', color: '#fff' }} />
                                    <Bar dataKey="count" fill="#ef4444" radius={[4, 4, 0, 0]} opacity={0.8} />
                                </BarChart>
                            </ResponsiveContainer>
                        </motion.div>
                    )}

                    {activeTab === 'after' && (
                        <motion.div key="after" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full w-full">
                            <h3 className="text-sm font-semibold text-green-400 mb-4">Whole Dataset Integrity (Sanitized Bell Curve)</h3>
                            {!data.global_clean_hist || data.global_clean_hist.length === 0 ? (
                                <div className="h-full flex flex-col items-center justify-center text-neutral-500 border-2 border-dashed border-neutral-800 rounded-2xl bg-neutral-900/20">
                                    <ShieldCheck className="w-12 h-12 mb-3 opacity-30" />
                                    <p className="font-medium text-neutral-400">No Cleaned Data Available</p>
                                    <p className="text-sm mt-1 text-center max-w-xs">Please visit the "Cleaning" tab and apply a sanitization strategy first.</p>
                                </div>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data.global_clean_hist} margin={{ bottom: 20 }}>
                                        <XAxis dataKey="bin" stroke="#525252" fontSize={10} angle={-45} textAnchor="end" />
                                        <YAxis hide />
                                        <Tooltip contentStyle={{ backgroundColor: '#171717', border: 'none', color: '#fff' }} />
                                        <Bar dataKey="count" fill="#22c55e" radius={[4, 4, 0, 0]} opacity={0.8} />
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </motion.div>
                    )}

                    {activeTab === 'correlation' && (
                        <motion.div key="corr" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full w-full flex flex-col">
                            <div className="mb-4 flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-blue-400">Trendline Analysis</h3>
                                <div className="px-4 py-1.5 rounded-full text-xs font-bold border bg-neutral-800 text-white">
                                    {correlationData.status} (r = {correlationData.r})
                                </div>
                            </div>
                            {!data.clean_sample || data.clean_sample.length === 0 ? (
                                <div className="flex-1 flex flex-col items-center justify-center text-neutral-500 border-2 border-dashed border-neutral-800 rounded-2xl bg-neutral-900/20">
                                    <Zap className="w-12 h-12 mb-3 opacity-30" />
                                    <p className="font-medium text-neutral-400">Sanitization Required</p>
                                    <p className="text-sm mt-1">Correlation analysis requires a cleaned dataset. Apply a cleaning strategy first.</p>
                                </div>
                            ) : (
                                <div className="flex-1 min-h-0">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ComposedChart data={correlationData.points} margin={{ left: -20 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                                            <XAxis dataKey={corrX} type="number" stroke="#525252" fontSize={12} domain={['auto', 'auto']} />
                                            <YAxis dataKey={corrY} type="number" stroke="#525252" fontSize={12} domain={['auto', 'auto']} />
                                            <Tooltip contentStyle={{ backgroundColor: '#171717', border: 'none', color: '#fff' }} cursor={{ strokeDasharray: '3 3' }} />
                                            <Scatter name="Data Points" dataKey={corrY} fill="#60a5fa" opacity={0.6} />
                                            <Line name="Trendline" type="monotone" dataKey="trendLine" stroke="#facc15" strokeWidth={3} dot={false} />
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </div>
                            )}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}