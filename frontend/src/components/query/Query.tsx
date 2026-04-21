/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Terminal, Send, Loader2, Database, ShieldAlert, CheckCircle,
  Download, User, Bot, AlertCircle, BarChart3, TableProperties, Sparkles, BookOpen, X,
  DatabaseZap, ShieldCheck, Activity
} from 'lucide-react';
import { API_BASE } from '@/constants/config';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export interface QueryProps {
  sessionId: string;
}

export interface QueryMessage {
  id: string;
  role: 'user' | 'assistant';
  type: 'text' | 'status' | 'error' | 'explore_result' | 'pending_edit' | 'success_edit';
  content?: string;
  sql?: string;
  columns?: string[];
  data?: Record<string, unknown>[];
  rowsAffected?: number;
  suggestions?: string[];
}

export interface AuditLog {
  timestamp: string;
  session_id: string;
  prompt: string;
  sql: string;
  affected: number;
  status: string;
  error: string;
}

/* ─── Smart Result & Chart Viewer ────────────────────────────────────────────────────────── */

const ResultViewer = ({
  columns, dataRows, isEdit, suggestions, onSuggestionClick
}: {
  columns: string[], dataRows: Record<string, unknown>[], isEdit: boolean, suggestions?: string[], onSuggestionClick: (q: string) => void
}) => {
  const [view, setView] = useState<'table' | 'chart'>('table');

  const stringCol = columns.find(c => dataRows.length > 0 && typeof dataRows[0][c] === 'string');
  const numCol = columns.find(c => dataRows.length > 0 && typeof dataRows[0][c] === 'number');
  const canChart = !!(stringCol && numCol && dataRows.length <= 100);

  const colors = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4'];

  return (
    <div className="mt-3 flex flex-col w-full animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className={`flex items-center justify-between text-xs p-2 border border-b-0 rounded-t-xl ${isEdit ? 'bg-green-500/10 border-green-900/50 text-green-400' : 'bg-neutral-900 border-neutral-800 text-neutral-400'}`}>
        <div className="flex items-center font-mono uppercase px-2">
          <Database className="w-3 h-3 mr-2" />
          {isEdit ? 'Affected Rows' : `Results (${dataRows.length} rows)`}
        </div>
        {canChart && !isEdit && (
          <div className="flex bg-black p-1 rounded-lg border border-neutral-800">
            <button onClick={() => setView('table')} className={`px-3 py-1 rounded flex items-center transition-colors ${view === 'table' ? 'bg-neutral-800 text-white' : 'hover:text-white'}`}>
              <TableProperties className="w-3 h-3 mr-1.5" /> Table
            </button>
            <button onClick={() => setView('chart')} className={`px-3 py-1 rounded flex items-center transition-colors ${view === 'chart' ? 'bg-neutral-800 text-white' : 'hover:text-white'}`}>
              <BarChart3 className="w-3 h-3 mr-1.5" /> Chart
            </button>
          </div>
        )}
      </div>

      <div className={`border rounded-b-xl overflow-hidden ${isEdit ? 'border-green-900/50' : 'border-neutral-800 bg-[#0A0A0A]'}`}>
        {view === 'table' ? (
          <div className="max-h-64 overflow-y-auto overflow-x-auto custom-scrollbar" data-lenis-prevent>
            <table className="w-full text-sm text-left text-neutral-300">
              <thead className={`text-xs uppercase sticky top-0 z-10 ${isEdit ? 'bg-green-950 text-green-500' : 'bg-neutral-900 text-neutral-500'}`}>
                <tr>
                  {columns.map(col => (
                    <th key={col} className={`px-4 py-2 border-b whitespace-nowrap ${isEdit ? 'border-green-900/30' : 'border-neutral-800'}`}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dataRows.length === 0 ? (
                  <tr>
                    <td colSpan={100} className="p-4 text-center text-neutral-500">No rows matched criteria.</td>
                  </tr>
                ) : (
                  dataRows.map((row, i) => (
                    <tr key={i} className={`border-b hover:bg-white/5 ${isEdit ? 'border-green-900/30' : 'border-neutral-800/50'}`}>
                      {columns.map(col => (
                        <td key={col} className="px-4 py-2 font-mono whitespace-nowrap">
                          {row[col] === null || row[col] === undefined ? <span className="text-neutral-600 italic">—</span> : String(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="h-64 w-full p-4 bg-[#0A0A0A]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dataRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                <XAxis dataKey={stringCol!} stroke="#525252" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#525252" fontSize={11} tickLine={false} axisLine={false} />
                <RechartsTooltip cursor={{ fill: '#171717' }} contentStyle={{ backgroundColor: '#000', border: '1px solid #262626', borderRadius: '8px', fontSize: '12px' }} />
                <Bar dataKey={numCol!} radius={[4, 4, 0, 0]}>
                  {dataRows.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {suggestions && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-4 animate-in fade-in slide-in-from-bottom-2 duration-700 delay-300">
          {suggestions.map((sugg, idx) => (
            <button
              key={idx}
              onClick={() => onSuggestionClick(sugg)}
              className="flex items-center text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 px-3 py-1.5 rounded-full hover:bg-blue-500/20 hover:border-blue-500/40 transition-all active:scale-95"
            >
              <Sparkles className="w-3 h-3 mr-1.5" /> {sugg}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/* ─── Component ──────────────────────────────────────────────────────────────────────────── */

export default function Query({ sessionId }: QueryProps): React.JSX.Element {
  const [queryText, setQueryText] = useState('');
  const [mode, setMode] = useState<'explore' | 'edit'>('explore');
  const [messages, setMessages] = useState<QueryMessage[]>([{
    id: 'welcome', role: 'assistant', type: 'text',
    content: 'DataSentinel Neuro-Symbolic Agent online. How can I help you analyze this dataset?',
  }]);
  const [isLoading, setIsLoading] = useState(false);

  // Option 3: Teach Modal State
  const [isTeachModalOpen, setIsTeachModalOpen] = useState(false);
  const [teachForm, setTeachForm] = useState({ term: '', logic: '', description: '', keywords: '' });
  const [isTeaching, setIsTeaching] = useState(false);

  // Option 4.1: Connect Live DB State
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [dbUri, setDbUri] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);

  // Option 4.2: Fetch Audit Logs State
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const submitQuery = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: QueryMessage = { id: Date.now().toString(), role: 'user', type: 'text', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setQueryText('');

    try {
      const response = await fetch(`${API_BASE}/api/query/${sessionId}?user_query=${encodeURIComponent(userMsg.content || '')}&mode=${mode}`, {
        method: 'POST',
      });

      if (!response.body) throw new Error("No response body returned from server.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const currentStatusId = Date.now().toString() + '-status';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.replace('data: ', ''));

              if (data.error) {
                setMessages(prev => [...prev.filter(m => m.id !== currentStatusId), { id: Date.now().toString(), role: 'assistant', type: 'error', content: data.error }]);
                setIsLoading(false);
                return;
              }

              if (data.status === 'Complete') {
                setMessages(prev => prev.filter(m => m.id !== currentStatusId));

                if (mode === 'edit') {
                  setMessages(prev => [...prev, {
                    id: Date.now().toString(), role: 'assistant', type: 'pending_edit', sql: data.sql,
                    content: 'Query generated. Awaiting execution confirmation.'
                  }]);
                } else {
                  setMessages(prev => [...prev, {
                    id: Date.now().toString(), role: 'assistant', type: 'explore_result', sql: data.sql,
                    columns: data.columns, data: data.data, suggestions: data.suggestions, content: 'Here are the results.'
                  }]);
                }
                setIsLoading(false);
              } else if (data.status) {
                setMessages(prev => {
                  const lastMsg = prev[prev.length - 1];
                  if (lastMsg && lastMsg.type === 'status') {
                    return [...prev.slice(0, -1), { ...lastMsg, content: data.status }];
                  }
                  return [...prev, { id: currentStatusId, role: 'assistant', type: 'status', content: data.status }];
                });
              }
            } catch (err) {
              console.error("Failed to parse SSE", err);
            }
          }
        }
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to connect to agent.";
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', type: 'error', content: errorMessage }]);
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    submitQuery(queryText);
  };

  const executeEdit = async (msgId: string, sql: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/confirm-edit/${sessionId}?sql_query=${encodeURIComponent(sql)}`, { method: 'POST' });
      const data = await response.json();

      setMessages(prev => prev.map(msg => {
        if (msg.id === msgId) {
          if (data.error) return { ...msg, type: 'error', content: data.error };
          return { ...msg, type: 'success_edit', rowsAffected: data.rows_affected, columns: data.columns, data: data.preview_data, content: 'Database updated.' };
        }
        return msg;
      }));
    } catch (error: unknown) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTeachSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsTeaching(true);
    try {
      const payload = {
        ...teachForm,
        keywords: teachForm.keywords.split(',').map(k => k.trim()).filter(Boolean)
      };
      const response = await fetch(`${API_BASE}/api/knowledge/learn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (response.ok) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(), role: 'assistant', type: 'text',
          content: `🧠 I have successfully learned the rule for "${teachForm.term}". I will use this context in future queries.`
        }]);
        setIsTeachModalOpen(false);
        setTeachForm({ term: '', logic: '', description: '', keywords: '' });
      }
    } catch (error) {
      console.error(error);
    } finally {
      setIsTeaching(false);
    }
  };

  const handleConnectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsConnecting(true);
    try {
      const response = await fetch(`${API_BASE}/api/connect-db/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uri: dbUri })
      });
      const data = await response.json();
      if (response.ok) {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', type: 'text', content: `🔌 ${data.message}` }]);
        setIsConnectModalOpen(false);
        setDbUri('');
      } else {
        alert(data.error || "Connection failed.");
      }
    } catch (error) {
      console.error(error);
    } finally {
      setIsConnecting(false);
    }
  };

  const openAuditModal = async () => {
    setIsAuditModalOpen(true);
    setIsLoadingLogs(true);
    try {
      const response = await fetch(`${API_BASE}/api/admin/audit-logs`);
      const data = await response.json();
      if (data.logs) setAuditLogs(data.logs);
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoadingLogs(false);
    }
  };

  return (
    <div className="relative w-full mt-6 bg-[#050505] border border-neutral-800 rounded-2xl flex flex-col h-[750px] overflow-hidden shadow-2xl">

      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-neutral-900/50 border-b border-neutral-800 shrink-0">
        <div className="flex items-center mb-4 md:mb-0">
          <div className="p-2 bg-neutral-800 rounded-lg mr-3 shadow-inner shadow-white/5 border border-neutral-700">
            <Terminal className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-md font-bold tracking-wide leading-tight text-white flex items-center">
              DataSentinel Core
              <span className="ml-2 px-2 py-0.5 rounded text-[10px] font-mono bg-blue-500/20 text-blue-400 border border-blue-500/30">AGENTIC RAG</span>
            </h3>
            <p className="text-xs font-mono text-neutral-500 flex items-center mt-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse mr-1.5 shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
              System Online
            </p>
          </div>
        </div>

        {/* Right Controls */}
        <div className="flex items-center space-x-2 overflow-x-auto custom-scrollbar pb-2 md:pb-0">
          <button onClick={() => setIsConnectModalOpen(true)} className="flex items-center px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 rounded-lg text-xs font-bold transition-all whitespace-nowrap">
            <DatabaseZap className="w-3.5 h-3.5 mr-2" /> Live DB
          </button>

          <button onClick={() => setIsTeachModalOpen(true)} className="flex items-center px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 rounded-lg text-xs font-bold transition-all whitespace-nowrap">
            <BookOpen className="w-3.5 h-3.5 mr-2" /> Teach AI
          </button>

          <button onClick={openAuditModal} className="flex items-center px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-white rounded-lg text-xs font-medium transition-colors whitespace-nowrap">
            <ShieldCheck className="w-3.5 h-3.5 mr-1.5" /> Logs
          </button>

          <button onClick={() => window.open(`${API_BASE}/api/download/${sessionId}`, '_blank')} className="flex items-center px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-white rounded-lg text-xs font-medium transition-colors whitespace-nowrap">
            <Download className="w-3.5 h-3.5" />
          </button>

          <div className="h-6 w-px bg-neutral-800 mx-1 shrink-0" />

          <div className="flex bg-black p-1 rounded-xl border border-neutral-800 shrink-0">
            <button onClick={() => setMode('explore')} className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-colors ${mode === 'explore' ? 'bg-blue-500/20 text-blue-400' : 'text-neutral-500 hover:text-white'}`}>Explore</button>
            <button onClick={() => setMode('edit')} className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center ${mode === 'edit' ? 'bg-red-500/20 text-red-400' : 'text-neutral-500 hover:text-white'}`}><ShieldAlert className="w-3 h-3 mr-1.5" /> Modify</button>
          </div>
        </div>
      </div>

      {/* CHAT AREA */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 custom-scrollbar bg-[#0A0A0A]" data-lenis-prevent>
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div key={msg.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center border border-neutral-700 mr-3 shrink-0 mt-1 shadow-md">
                  <Bot className="w-4 h-4 text-neutral-400" />
                </div>
              )}
              <div className={`max-w-[95%] md:max-w-[85%] ${msg.role === 'user' ? 'bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-sm shadow-md' : 'w-full'}`}>
                {msg.role === 'user' && <p className="text-sm">{msg.content}</p>}

                {msg.type === 'status' && (
                  <div className="flex items-center text-cyan-400 font-mono text-xs bg-cyan-900/10 p-3 rounded-xl border border-cyan-900/30 w-fit backdrop-blur-sm">
                    <Loader2 className="w-4 h-4 mr-2 shrink-0 animate-spin" /> {msg.content}
                  </div>
                )}

                {msg.type === 'text' && <div className="text-sm text-neutral-300 mt-1 leading-relaxed">{msg.content}</div>}

                {msg.type === 'error' && (
                  <div className="flex items-start text-red-400 bg-red-500/10 border border-red-900/50 p-4 rounded-xl text-sm">
                    <AlertCircle className="w-5 h-5 mr-2 shrink-0 mt-0.5" /> {msg.content}
                  </div>
                )}

                {msg.type === 'explore_result' && msg.columns && msg.data && (
                  <>
                    <div className="text-xs text-neutral-500 font-mono mb-1 bg-neutral-900 p-2 rounded border border-neutral-800 inline-block w-fit">
                      Executed: {msg.sql}
                    </div>
                    <ResultViewer columns={msg.columns} dataRows={msg.data} isEdit={false} suggestions={msg.suggestions} onSuggestionClick={submitQuery} />
                  </>
                )}

                {msg.type === 'pending_edit' && (
                  <div className="p-5 bg-red-500/5 border border-red-900/30 rounded-2xl w-full max-w-2xl mt-2">
                    <h4 className="text-red-400 font-bold flex items-center mb-2"><ShieldAlert className="w-5 h-5 mr-2" /> Confirm Modification</h4>
                    <p className="text-sm text-neutral-400 mb-4">Please review the SQL before executing. This permanently alters the dataset.</p>
                    <code className="block p-4 bg-black rounded-xl border border-neutral-800 text-red-400 font-mono text-xs mb-4 overflow-x-auto whitespace-pre">{msg.sql}</code>
                    <button onClick={() => executeEdit(msg.id, msg.sql!)} className="px-6 py-2.5 bg-red-500 text-black font-bold rounded-lg hover:bg-red-400 transition-colors text-sm shadow-[0_0_15px_rgba(239,68,68,0.3)]">Yes, Execute Mutation</button>
                  </div>
                )}

                {msg.type === 'success_edit' && msg.columns && msg.data && (
                  <>
                    <div className="flex items-center text-green-400 mb-2 font-medium text-sm mt-2"><CheckCircle className="w-5 h-5 mr-2" /> Successfully modified {msg.rowsAffected} rows.</div>
                    <ResultViewer columns={msg.columns} dataRows={msg.data} isEdit={true} onSuggestionClick={() => { }} />
                  </>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30 ml-3 shrink-0 mt-1">
                  <User className="w-4 h-4 text-blue-400" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={messagesEndRef} className="h-1" />
      </div>

      {/* INPUT AREA */}
      <div className="p-4 bg-neutral-900/80 border-t border-neutral-800 shrink-0 backdrop-blur-md">
        <form onSubmit={handleSearch} className="relative max-w-4xl mx-auto flex items-center">
          <input
            type="text"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            disabled={isLoading}
            placeholder={mode === 'explore' ? 'Ask a question about the data...' : 'Command the AI to modify the dataset (e.g. Delete all test users)...'}
            className={`w-full bg-[#050505] border text-white rounded-xl pl-5 pr-14 py-4 outline-none transition-colors text-sm shadow-inner focus:ring-2 focus:ring-opacity-20 ${mode === 'edit' ? 'border-red-900/50 focus:border-red-500 focus:ring-red-500' : 'border-neutral-700 focus:border-blue-500 focus:ring-blue-500'}`}
          />
          <button type="submit" disabled={isLoading || !queryText.trim()} className={`absolute right-2 p-2.5 rounded-lg disabled:opacity-50 transition-all active:scale-95 ${mode === 'edit' ? 'bg-red-500 text-black hover:bg-red-400' : 'bg-blue-600 text-white hover:bg-blue-500'}`}>
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

      {/* ── MODALS ── */}

      {/* 1. Teach Agent Modal */}
      <AnimatePresence>
        {isTeachModalOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }}
              className="bg-neutral-900 border border-neutral-700 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl"
            >
              <div className="flex justify-between items-center p-4 border-b border-neutral-800 bg-neutral-950">
                <h3 className="font-bold flex items-center text-indigo-400">
                  <BookOpen className="w-4 h-4 mr-2" /> Teach the Agent
                </h3>
                <button onClick={() => setIsTeachModalOpen(false)} className="text-neutral-500 hover:text-white p-1">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <form onSubmit={handleTeachSubmit} className="p-5 space-y-4">
                <div>
                  <label className="block text-xs font-bold text-neutral-400 mb-1 uppercase tracking-wider">Business Term</label>
                  <input required value={teachForm.term} onChange={e => setTeachForm(f => ({ ...f, term: e.target.value }))} placeholder="e.g. VIP Customer" className="w-full bg-black border border-neutral-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-neutral-400 mb-1 uppercase tracking-wider">SQL Logic</label>
                  <input required value={teachForm.logic} onChange={e => setTeachForm(f => ({ ...f, logic: e.target.value }))} placeholder="e.g. total_spent > 1000 AND status = 'active'" className="w-full bg-black border border-neutral-800 rounded-lg px-3 py-2 text-sm text-white font-mono outline-none focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-neutral-400 mb-1 uppercase tracking-wider">Keywords (comma separated)</label>
                  <input required value={teachForm.keywords} onChange={e => setTeachForm(f => ({ ...f, keywords: e.target.value }))} placeholder="e.g. vip, whale, high value" className="w-full bg-black border border-neutral-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-neutral-400 mb-1 uppercase tracking-wider">Description</label>
                  <textarea required value={teachForm.description} onChange={e => setTeachForm(f => ({ ...f, description: e.target.value }))} placeholder="Briefly explain what this rule means..." className="w-full bg-black border border-neutral-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500 min-h-[80px]" />
                </div>
                <div className="pt-2 flex justify-end">
                  <button type="button" onClick={() => setIsTeachModalOpen(false)} className="px-4 py-2 text-sm font-medium text-neutral-400 hover:text-white mr-2">Cancel</button>
                  <button type="submit" disabled={isTeaching} className="flex items-center px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-lg transition-colors disabled:opacity-50">
                    {isTeaching ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : 'Save Rule'}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 2. Connect DB Modal */}
      <AnimatePresence>
        {isConnectModalOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }} className="bg-neutral-900 border border-neutral-700 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
              <div className="flex justify-between items-center p-4 border-b border-neutral-800 bg-neutral-950">
                <h3 className="font-bold flex items-center text-emerald-400"><DatabaseZap className="w-4 h-4 mr-2" /> Connect Live Database</h3>
                <button onClick={() => setIsConnectModalOpen(false)} className="text-neutral-500 hover:text-white p-1"><X className="w-5 h-5" /></button>
              </div>
              <form onSubmit={handleConnectSubmit} className="p-5 space-y-4">
                <p className="text-sm text-neutral-400">Provide a PostgreSQL connection string to allow the AI to query production tables in real-time without moving data.</p>
                <div>
                  <label className="block text-xs font-bold text-neutral-400 mb-1 uppercase">PostgreSQL URI</label>
                  <input required type="text" value={dbUri} onChange={e => setDbUri(e.target.value)} placeholder="postgresql://user:pass@localhost:5432/mydb" className="w-full bg-black border border-neutral-800 rounded-lg px-3 py-3 text-sm text-white font-mono outline-none focus:border-emerald-500" />
                </div>
                <div className="pt-2 flex justify-end">
                  <button type="button" onClick={() => setIsConnectModalOpen(false)} className="px-4 py-2 text-sm font-medium text-neutral-400 hover:text-white mr-2">Cancel</button>
                  <button type="submit" disabled={isConnecting} className="flex items-center px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold rounded-lg transition-colors">{isConnecting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : 'Connect Server'}</button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 3. Audit Trail Modal */}
      <AnimatePresence>
        {isAuditModalOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              /* ADDED overflow-hidden HERE */
              className="bg-neutral-900 border border-neutral-700 rounded-2xl w-full max-w-4xl max-h-[80vh] flex flex-col shadow-2xl overflow-hidden"
            >
              <div className="flex justify-between items-center p-4 border-b border-neutral-800 bg-neutral-950 shrink-0">
                <h3 className="font-bold flex items-center text-white"><ShieldCheck className="w-5 h-5 mr-2 text-blue-500" /> Security Audit Trail (SOC2)</h3>
                <button onClick={() => setIsAuditModalOpen(false)} className="text-neutral-500 hover:text-white p-1"><X className="w-5 h-5" /></button>
              </div>

              {/* ADDED data-lenis-prevent HERE */}
              <div className="p-4 flex-1 overflow-y-auto custom-scrollbar bg-[#050505]" data-lenis-prevent>
                {isLoadingLogs ? (
                  <div className="flex items-center justify-center h-40 text-neutral-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
                ) : auditLogs.length === 0 ? (
                  <div className="text-center py-10">
                    <Activity className="w-10 h-10 text-neutral-800 mx-auto mb-3" />
                    <p className="text-neutral-500 text-sm">No mutations have been logged yet.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {auditLogs.map((log, i) => (
                      <div key={i} className="p-4 bg-neutral-900 border border-neutral-800 rounded-xl hover:border-neutral-700 transition-colors">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-mono text-cyan-500 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">{log.timestamp}</span>
                          <span className={`text-xs font-bold px-2 py-0.5 rounded ${log.status === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                            {log.status.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-white mb-2"><span className="text-neutral-500">Action:</span> {log.prompt}</p>
                        <code className="block w-full p-3 bg-black border border-neutral-800 rounded-lg text-neutral-300 font-mono text-xs overflow-x-auto whitespace-pre">{log.sql}</code>
                        <div className="mt-3 flex items-center text-xs">
                          <span className="text-neutral-500">Session ID: <span className="text-neutral-300">{log.session_id.substring(0, 8)}...</span></span>
                          <span className="mx-3 text-neutral-700">•</span>
                          <span className="text-neutral-500">Rows Affected: <span className="text-white font-bold">{log.affected}</span></span>
                        </div>
                        {log.error && (
                          <div className="mt-2 text-xs text-red-400 bg-red-500/10 p-2 rounded border border-red-500/20">{log.error}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}