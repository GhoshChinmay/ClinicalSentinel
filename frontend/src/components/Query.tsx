import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, Send, Loader2, Database, ShieldAlert, CheckCircle, Download, User, Bot, AlertCircle } from 'lucide-react';

type Message = {
    id: string;
    role: 'user' | 'assistant';
    type: 'text' | 'explore_result' | 'pending_edit' | 'success_edit' | 'error';
    content?: string;
    sql?: string;
    columns?: string[];
    data?: any[];
    rowsAffected?: number;
};

// Bulletproof ID generator to prevent React Key collisions
const generateId = () => Date.now().toString(36) + Math.random().toString(36).substring(2, 9);

export default function Query({ sessionId }: { sessionId: string }) {
    const [query, setQuery] = useState("");
    const [mode, setMode] = useState<'explore' | 'edit'>('explore');
    const [messages, setMessages] = useState<Message[]>([
        { id: 'welcome', role: 'assistant', type: 'text', content: 'System initialized. What would you like to know about your data, or what would you like to change?' }
    ]);
    const [loading, setLoading] = useState(false);

    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to the bottom whenever a new message is added
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;

        const userMsgId = generateId();
        const newUserMsg: Message = { id: userMsgId, role: 'user', type: 'text', content: query };
        setMessages(prev => [...prev, newUserMsg]);
        setQuery("");
        setLoading(true);

        try {
            const res = await axios.post(`http://127.0.0.1:8000/api/query/${sessionId}`, {
                user_query: newUserMsg.content,
                is_edit: mode === 'edit'
            });

            const aiMsgId = generateId();
            if (mode === 'edit') {
                setMessages(prev => [...prev, { id: aiMsgId, role: 'assistant', type: 'pending_edit', sql: res.data.sql }]);
            } else {
                setMessages(prev => [...prev, { id: aiMsgId, role: 'assistant', type: 'explore_result', sql: res.data.sql, columns: res.data.columns, data: res.data.data }]);
            }
        } catch (err: any) {
            setMessages(prev => [...prev, { id: generateId(), role: 'assistant', type: 'error', content: err.response?.data?.detail || "Failed to process query." }]);
        } finally {
            setLoading(false);
        }
    };

    const executeEdit = async (messageId: string, sqlQuery: string) => {
        setLoading(true);
        try {
            const res = await axios.post(`http://127.0.0.1:8000/api/query_edit/confirm/${sessionId}`, { sql_query: sqlQuery });

            // Update the specific pending message to a success message
            setMessages(prev => prev.map(msg =>
                msg.id === messageId
                    ? { ...msg, type: 'success_edit', rowsAffected: res.data.rows_affected, columns: res.data.columns, data: res.data.preview_data }
                    : msg
            ));
        } catch (err: any) {
            setMessages(prev => [...prev, { id: generateId(), role: 'assistant', type: 'error', content: err.response?.data?.detail || "Execution failed." }]);
        } finally {
            setLoading(false);
        }
    };

    const renderDataTable = (columns: string[], data: any[], isEdit: boolean) => (
        <div className={`mt-3 border rounded-xl overflow-hidden overflow-x-auto ${isEdit ? 'bg-green-500/5 border-green-900/50' : 'bg-[#0A0A0A] border-neutral-800'}`}>
            <div className={`flex items-center text-xs p-3 border-b font-mono uppercase ${isEdit ? 'text-green-400 border-green-900/50' : 'text-neutral-500 border-neutral-800'}`}>
                <Database className="w-3 h-3 mr-2" />
                {isEdit ? 'Affected Rows Preview' : `Results (${data.length} rows)`}
            </div>
            <div className="max-h-64 overflow-y-auto custom-scrollbar">
                <table className="w-full text-sm text-left text-neutral-300">
                    <thead className={`text-xs uppercase sticky top-0 ${isEdit ? 'bg-green-900/40 text-green-500' : 'bg-neutral-900 text-neutral-500'}`}>
                        <tr>{columns.map((col: string) => <th key={col} className={`px-4 py-2 border-b whitespace-nowrap ${isEdit ? 'border-green-900/30' : 'border-neutral-800'}`}>{col}</th>)}</tr>
                    </thead>
                    <tbody>
                        {data.length === 0 ? (
                            <tr><td colSpan={100} className="p-4 text-center text-neutral-500">No rows matched criteria.</td></tr>
                        ) : (
                            data.map((row: any, i: number) => (
                                <tr key={i} className={`border-b hover:bg-white/5 ${isEdit ? 'border-green-900/30' : 'border-neutral-800/50'}`}>
                                    {columns.map((col: string) => <td key={col} className="px-4 py-2 font-mono whitespace-nowrap">{String(row[col])}</td>)}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );

    return (
        <div className="w-full mt-6 bg-[#050505] border border-neutral-800 rounded-2xl flex flex-col h-[700px] overflow-hidden shadow-2xl">

            {/* HEADER */}
            <div className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-neutral-900/50 border-b border-neutral-800 shrink-0">
                <div className="flex items-center mb-4 md:mb-0">
                    <div className="p-2 bg-neutral-800 rounded-lg mr-3"><Terminal className="w-5 h-5 text-white" /></div>
                    <div>
                        <h3 className="text-md font-semibold leading-tight">Data Co-Pilot</h3>
                        <p className="text-xs text-neutral-500">Session active. Ready for commands.</p>
                    </div>
                </div>
                <div className="flex items-center space-x-3">
                    {/* Permanent Download Button */}
                    <button onClick={() => window.open(`http://127.0.0.1:8000/api/download/${sessionId}`, '_blank')} className="flex items-center px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-white rounded-lg text-xs font-medium transition-colors">
                        <Download className="w-3.5 h-3.5 mr-2" /> Download File
                    </button>

                    <div className="h-6 w-px bg-neutral-700 mx-2"></div>

                    {/* Toggle Mode */}
                    <div className="flex bg-black p-1 rounded-xl border border-neutral-800">
                        <button onClick={() => setMode('explore')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${mode === 'explore' ? 'bg-blue-500/20 text-blue-400' : 'text-neutral-500 hover:text-white'}`}>
                            Explore
                        </button>
                        <button onClick={() => setMode('edit')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center ${mode === 'edit' ? 'bg-red-500/20 text-red-400' : 'text-neutral-500 hover:text-white'}`}>
                            <ShieldAlert className="w-3 h-3 mr-1" /> Modify
                        </button>
                    </div>
                </div>
            </div>

            {/* CHAT LOG AREA */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar bg-[#0A0A0A]">
                <AnimatePresence initial={false}>
                    {messages.map((msg) => (
                        <motion.div key={msg.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>

                            {/* AI Avatar */}
                            {msg.role === 'assistant' && (
                                <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center border border-neutral-700 mr-3 shrink-0">
                                    <Bot className="w-4 h-4 text-neutral-400" />
                                </div>
                            )}

                            <div className={`max-w-[85%] ${msg.role === 'user' ? 'bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-sm shadow-md' : 'w-full'}`}>

                                {/* User Text */}
                                {msg.role === 'user' && <p className="text-sm">{msg.content}</p>}

                                {/* AI: Standard Text or Error */}
                                {msg.type === 'text' && <div className="text-sm text-neutral-300 mt-1">{msg.content}</div>}
                                {msg.type === 'error' && (
                                    <div className="flex items-start text-red-400 bg-red-500/10 border border-red-900/50 p-4 rounded-xl text-sm">
                                        <AlertCircle className="w-5 h-5 mr-2 shrink-0 mt-0.5" /> {msg.content}
                                    </div>
                                )}

                                {/* AI: Explore Result */}
                                {msg.type === 'explore_result' && (
                                    <div className="flex flex-col w-full">
                                        <div className="text-xs text-neutral-500 font-mono mb-2 bg-neutral-900 p-2 rounded border border-neutral-800 inline-block w-fit">Executed: {msg.sql}</div>
                                        {msg.columns && msg.data && renderDataTable(msg.columns, msg.data, false)}
                                    </div>
                                )}

                                {/* AI: Pending Edit Confirmation */}
                                {msg.type === 'pending_edit' && (
                                    <div className="p-5 bg-red-500/5 border border-red-900/30 rounded-2xl w-full max-w-2xl">
                                        <h4 className="text-red-400 font-bold flex items-center mb-2"><ShieldAlert className="w-5 h-5 mr-2" /> Confirm Dataset Modification</h4>
                                        <p className="text-sm text-neutral-400 mb-4">Please review the SQL query before executing. This will permanently alter the dataset.</p>
                                        <code className="block p-4 bg-black rounded-xl border border-neutral-800 text-red-400 font-mono text-xs mb-4">{msg.sql}</code>
                                        <button onClick={() => executeEdit(msg.id, msg.sql!)} className="px-6 py-2.5 bg-red-500 text-black font-bold rounded-lg hover:bg-red-400 transition-colors text-sm">
                                            Yes, Execute Query
                                        </button>
                                    </div>
                                )}

                                {/* AI: Success Edit Result */}
                                {msg.type === 'success_edit' && (
                                    <div className="flex flex-col w-full">
                                        <div className="flex items-center text-green-400 mb-2 font-medium text-sm">
                                            <CheckCircle className="w-5 h-5 mr-2" />
                                            Successfully modified {msg.rowsAffected} rows.
                                        </div>
                                        {msg.columns && msg.data && renderDataTable(msg.columns, msg.data, true)}
                                    </div>
                                )}

                            </div>

                            {/* User Avatar */}
                            {msg.role === 'user' && (
                                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30 ml-3 shrink-0">
                                    <User className="w-4 h-4 text-blue-400" />
                                </div>
                            )}
                        </motion.div>
                    ))}

                    {/* FIX: Added key="loading-bubble" to satisfy AnimatePresence */}
                    {loading && (
                        <motion.div key="loading-bubble" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex justify-start">
                            <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center border border-neutral-700 mr-3 shrink-0">
                                <Bot className="w-4 h-4 text-neutral-400" />
                            </div>
                            <div className="bg-neutral-900 border border-neutral-800 px-5 py-3 rounded-2xl rounded-tl-sm flex items-center space-x-2">
                                <Loader2 className="w-4 h-4 animate-spin text-neutral-500" />
                                <span className="text-sm text-neutral-500 font-medium tracking-wide">Processing logic...</span>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* FIX: Moved outside AnimatePresence so it doesn't need a key tracked for animation */}
                <div ref={messagesEndRef} className="h-1" />
            </div>

            {/* INPUT AREA */}
            <div className="p-4 bg-neutral-900/80 border-t border-neutral-800 shrink-0">
                <form onSubmit={handleSearch} className="relative max-w-4xl mx-auto flex items-center">
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        disabled={loading}
                        placeholder={mode === 'explore' ? "Ask a question about the data..." : "Command the AI to modify the dataset..."}
                        className={`w-full bg-[#050505] border text-white rounded-xl pl-4 pr-14 py-3.5 outline-none transition-colors text-sm focus:ring-2 focus:ring-opacity-20 ${mode === 'edit' ? 'border-red-900/50 focus:border-red-500 focus:ring-red-500' : 'border-neutral-700 focus:border-blue-500 focus:ring-blue-500'}`}
                    />
                    <button type="submit" disabled={loading || !query.trim()} className={`absolute right-2 p-2 rounded-lg disabled:opacity-50 transition-colors ${mode === 'edit' ? 'bg-red-500 text-black hover:bg-red-400' : 'bg-blue-600 text-white hover:bg-blue-500'}`}>
                        <Send className="w-4 h-4" />
                    </button>
                </form>
                <div className="text-center mt-2">
                    <span className="text-[10px] text-neutral-600 uppercase tracking-widest font-bold">Llama 3 Local AI Active</span>
                </div>
            </div>

        </div>
    );
}