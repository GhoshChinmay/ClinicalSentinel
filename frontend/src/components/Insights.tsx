import { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Bot, Sparkles, Loader2, AlertCircle } from 'lucide-react';

export default function Insights({ sessionId }: { sessionId: string }) {
    const [insights, setInsights] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchInsights = async () => {
            try {
                const res = await axios.get(`http://127.0.0.1:8000/api/insights/${sessionId}`);
                setInsights(res.data.insights);
            } catch (err: any) {
                setError(err.response?.data?.detail || "Failed to generate AI insights.");
            } finally {
                setLoading(false);
            }
        };

        if (sessionId) fetchInsights();
    }, [sessionId]);

    return (
        <div className="w-full mt-6">
            <div className="bg-[#0A0A0A] border border-neutral-800 rounded-2xl overflow-hidden p-8 relative">

                {/* Decorative Background */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20"></div>

                <div className="flex items-center mb-6 border-b border-neutral-800 pb-4">
                    <div className="p-3 bg-blue-500/10 rounded-xl mr-4 text-blue-400">
                        <Bot size={24} />
                    </div>
                    <div>
                        <h3 className="text-xl font-semibold text-white flex items-center">
                            Data Sentinel Intelligence <Sparkles className="w-4 h-4 ml-2 text-yellow-500" />
                        </h3>
                        <p className="text-sm text-neutral-400">Powered by Local Llama 3</p>
                    </div>
                </div>

                {loading && (
                    <div className="flex flex-col items-center justify-center py-12 text-blue-400">
                        <Loader2 className="w-8 h-8 animate-spin mb-4" />
                        <p className="animate-pulse">Reading dataset and generating expert insights...</p>
                        <p className="text-xs text-neutral-500 mt-2">(This may take 10-20 seconds on local hardware)</p>
                    </div>
                )}

                {error && (
                    <div className="flex items-center justify-center py-12 text-red-400 bg-red-500/5 rounded-xl border border-red-900/30">
                        <AlertCircle className="w-5 h-5 mr-2" />
                        {error}
                    </div>
                )}

                {insights && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="prose prose-invert max-w-none">
                        {/* Split the text by double newlines to create beautiful paragraphs automatically */}
                        {insights.split('\n\n').map((paragraph, idx) => (
                            <p key={idx} className="text-neutral-300 leading-relaxed text-[15px] mb-4">
                                {/* Bold any text surrounded by asterisks **like this** */}
                                {paragraph.split('**').map((chunk, i) => i % 2 === 1 ? <strong key={i} className="text-white">{chunk}</strong> : chunk)}
                            </p>
                        ))}
                    </motion.div>
                )}
            </div>
        </div>
    );
}