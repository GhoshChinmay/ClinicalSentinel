/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Terminal,
  Send,
  Loader2,
  Database,
  ShieldAlert,
  CheckCircle,
  Download,
  User,
  Bot,
  AlertCircle,
} from 'lucide-react';
import { API_BASE } from '@/constants/config';
import { useQueryData, type QueryMessage } from '@/hooks/use-query';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export interface QueryProps {
  sessionId: string;
}

/* ─── Shared Renderers ───────────────────────────────────────────────────────────────────── */

const renderDataTable = (columns: string[], dataRows: Record<string, unknown>[], isEdit: boolean) => (
  <div
    className={`mt-3 border rounded-xl overflow-hidden overflow-x-auto ${
      isEdit ? 'bg-green-500/5 border-green-900/50' : 'bg-[#0A0A0A] border-neutral-800'
    }`}
  >
    <div
      className={`flex items-center text-xs p-3 border-b font-mono uppercase ${
        isEdit ? 'text-green-400 border-green-900/50' : 'text-neutral-500 border-neutral-800'
      }`}
    >
      <Database className="w-3 h-3 mr-2" />
      {isEdit ? 'Affected Rows Preview' : `Results (${dataRows.length} rows)`}
    </div>
    <div className="max-h-64 overflow-y-auto custom-scrollbar">
      <table className="w-full text-sm text-left text-neutral-300">
        <thead
          className={`text-xs uppercase sticky top-0 ${
            isEdit ? 'bg-green-900/40 text-green-500' : 'bg-neutral-900 text-neutral-500'
          }`}
        >
          <tr>
            {columns.map((col: string) => (
              <th
                key={col}
                className={`px-4 py-2 border-b whitespace-nowrap ${
                  isEdit ? 'border-green-900/30' : 'border-neutral-800'
                }`}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataRows.length === 0 ? (
            <tr>
              <td colSpan={100} className="p-4 text-center text-neutral-500">
                No rows matched criteria.
              </td>
            </tr>
          ) : (
            dataRows.map((row: Record<string, unknown>, i: number) => (
              <tr
                key={i}
                className={`border-b hover:bg-white/5 ${
                  isEdit ? 'border-green-900/30' : 'border-neutral-800/50'
                }`}
              >
                {columns.map((col: string) => (
                  <td key={col} className="px-4 py-2 font-mono whitespace-nowrap">
                    {row[col] === null || row[col] === undefined ? (
                      <span className="text-neutral-600 italic">—</span>
                    ) : (
                      String(row[col])
                    )}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  </div>
);

const renderMessageContent = (msg: QueryMessage, executeEdit: (id: string, sql: string) => void) => {
  return (
    <>
      {msg.role === 'user' && <p className="text-sm">{msg.content}</p>}

      {msg.type === 'text' && <div className="text-sm text-neutral-300 mt-1">{msg.content}</div>}
      
      {msg.type === 'error' && (
        <div className="flex items-start text-red-400 bg-red-500/10 border border-red-900/50 p-4 rounded-xl text-sm">
          <AlertCircle className="w-5 h-5 mr-2 shrink-0 mt-0.5" /> {msg.content}
        </div>
      )}

      {msg.type === 'explore_result' && (
        <div className="flex flex-col w-full">
          <div className="text-xs text-neutral-500 font-mono mb-2 bg-neutral-900 p-2 rounded border border-neutral-800 inline-block w-fit">
            Executed: {msg.sql}
          </div>
          {msg.columns && msg.data && renderDataTable(msg.columns, msg.data, false)}
        </div>
      )}

      {msg.type === 'pending_edit' && (
        <div className="p-5 bg-red-500/5 border border-red-900/30 rounded-2xl w-full max-w-2xl">
          <h4 className="text-red-400 font-bold flex items-center mb-2">
            <ShieldAlert className="w-5 h-5 mr-2" /> Confirm Dataset Modification
          </h4>
          <p className="text-sm text-neutral-400 mb-4">
            Please review the SQL query before executing. This will permanently alter the dataset.
          </p>
          <code className="block p-4 bg-black rounded-xl border border-neutral-800 text-red-400 font-mono text-xs mb-4">
            {msg.sql}
          </code>
          <button
            onClick={() => executeEdit(msg.id, msg.sql!)}
            className="px-6 py-2.5 bg-red-500 text-black font-bold rounded-lg hover:bg-red-400 transition-colors text-sm"
          >
            Yes, Execute Query
          </button>
        </div>
      )}

      {msg.type === 'success_edit' && (
        <div className="flex flex-col w-full">
          <div className="flex items-center text-green-400 mb-2 font-medium text-sm">
            <CheckCircle className="w-5 h-5 mr-2" />
            Successfully modified {msg.rowsAffected} rows.
          </div>
          {msg.columns && msg.data && renderDataTable(msg.columns, msg.data, true)}
        </div>
      )}
    </>
  );
};

/* ─── Component ──────────────────────────────────────────────────────────────────────────── */

/**
 * Query component for natural language dataset exploration and modification.
 *
 * @param {QueryProps} props - The properties for the query component.
 * @returns {React.JSX.Element} The rendered interface.
 */
export default function Query({ sessionId }: QueryProps): React.JSX.Element {
  const {
    queryText,
    setQueryText,
    mode,
    setMode,
    messages,
    isLoading,
    handleSearch,
    executeEdit,
  } = useQueryData(sessionId);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="w-full mt-6 bg-[#050505] border border-neutral-800 rounded-2xl flex flex-col h-[700px] overflow-hidden shadow-2xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-neutral-900/50 border-b border-neutral-800 shrink-0">
        <div className="flex items-center mb-4 md:mb-0">
          <div className="p-2 bg-neutral-800 rounded-lg mr-3">
            <Terminal className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-md font-semibold leading-tight">Data Co-Pilot</h3>
            <p className="text-xs text-neutral-500">Session active. Ready for commands.</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => window.open(`${API_BASE}/api/download/${sessionId}`, '_blank')}
            className="flex items-center px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-white rounded-lg text-xs font-medium transition-colors"
          >
            <Download className="w-3.5 h-3.5 mr-2" /> Download File
          </button>
          <div className="h-6 w-px bg-neutral-700 mx-2" />
          <div className="flex bg-black p-1 rounded-xl border border-neutral-800">
            <button
              onClick={() => setMode('explore')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                mode === 'explore'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-neutral-500 hover:text-white'
              }`}
            >
              Explore
            </button>
            <button
              onClick={() => setMode('edit')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center ${
                mode === 'edit'
                  ? 'bg-red-500/20 text-red-400'
                  : 'text-neutral-500 hover:text-white'
              }`}
            >
              <ShieldAlert className="w-3 h-3 mr-1" /> Modify
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar bg-[#0A0A0A]">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center border border-neutral-700 mr-3 shrink-0">
                  <Bot className="w-4 h-4 text-neutral-400" />
                </div>
              )}

              <div
                className={`max-w-[85%] ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-sm shadow-md'
                    : 'w-full'
                }`}
              >
                {renderMessageContent(msg, executeEdit)}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30 ml-3 shrink-0">
                  <User className="w-4 h-4 text-blue-400" />
                </div>
              )}
            </motion.div>
          ))}

          {isLoading && (
            <motion.div
              key="loading-bubble"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex justify-start"
            >
              <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center border border-neutral-700 mr-3 shrink-0">
                <Bot className="w-4 h-4 text-neutral-400" />
              </div>
              <div className="bg-neutral-900 border border-neutral-800 px-5 py-3 rounded-2xl rounded-tl-sm flex items-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-neutral-500" />
                <span className="text-sm text-neutral-500 font-medium tracking-wide">
                  Processing logic...
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} className="h-1" />
      </div>

      <div className="p-4 bg-neutral-900/80 border-t border-neutral-800 shrink-0">
        <form onSubmit={handleSearch} className="relative max-w-4xl mx-auto flex items-center">
          <input
            type="text"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            disabled={isLoading}
            placeholder={
              mode === 'explore'
                ? 'Ask a question about the data...'
                : 'Command the AI to modify the dataset...'
            }
            className={`w-full bg-[#050505] border text-white rounded-xl pl-4 pr-14 py-3.5 outline-none transition-colors text-sm focus:ring-2 focus:ring-opacity-20 ${
              mode === 'edit'
                ? 'border-red-900/50 focus:border-red-500 focus:ring-red-500'
                : 'border-neutral-700 focus:border-blue-500 focus:ring-blue-500'
            }`}
          />
          <button
            type="submit"
            disabled={isLoading || !queryText.trim()}
            className={`absolute right-2 p-2 rounded-lg disabled:opacity-50 transition-colors ${
              mode === 'edit'
                ? 'bg-red-500 text-black hover:bg-red-400'
                : 'bg-blue-600 text-white hover:bg-blue-500'
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <div className="text-center mt-2">
          <span className="text-[10px] text-neutral-600 uppercase tracking-widest font-bold">
            Groq Cloud API Active
          </span>
        </div>
      </div>
    </div>
  );
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */
