/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useState } from 'react';
import api from '@/services/api.service';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export type QueryMode = 'explore' | 'edit';

export interface QueryMessage {
  id: string;
  role: 'user' | 'assistant';
  type: 'text' | 'explore_result' | 'pending_edit' | 'success_edit' | 'error';
  content?: string;
  sql?: string;
  columns?: string[];
  data?: Record<string, unknown>[];
  rowsAffected?: number;
}

/* ─── Helpers ────────────────────────────────────────────────────────────────────────────── */

export const generateId = (): string => {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 9);
};

/* ─── Hook ───────────────────────────────────────────────────────────────────────────────── */

export function useQueryData(sessionId: string) {
  const [queryText, setQueryText] = useState('');
  const [mode, setMode] = useState<QueryMode>('explore');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<QueryMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      type: 'text',
      content: 'System initialized. What would you like to know about your data, or what would you like to change?',
    },
  ]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryText.trim()) return;

    const userMsgId = generateId();
    const newUserMsg: QueryMessage = {
      id: userMsgId,
      role: 'user',
      type: 'text',
      content: queryText,
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setQueryText('');
    setIsLoading(true);

    try {
      const res = await api.post(
        `/api/query/${sessionId}?user_query=${encodeURIComponent(newUserMsg.content || '')}&mode=${mode}`
      );

      const aiMsgId = generateId();
      if (mode === 'edit') {
        setMessages((prev) => [
          ...prev,
          { id: aiMsgId, role: 'assistant', type: 'pending_edit', sql: res.data.sql },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: aiMsgId,
            role: 'assistant',
            type: 'explore_result',
            sql: res.data.sql,
            columns: res.data.columns,
            data: res.data.data,
          },
        ]);
      }
    } catch (err: unknown) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  };

  const executeEdit = async (messageId: string, sqlQuery: string) => {
    setIsLoading(true);
    try {
      const res = await api.post(
        `/api/confirm-edit/${sessionId}?sql_query=${encodeURIComponent(sqlQuery)}`
      );

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                type: 'success_edit',
                rowsAffected: res.data.rows_affected,
                columns: res.data.columns,
                data: res.data.preview_data,
              }
            : msg
        )
      );
    } catch (err: unknown) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleError = (err: unknown) => {
    let errorMsg = 'Execution failed.';
    const axiosErr = err as {
      response?: { data?: { error?: unknown; detail?: unknown } };
      message?: string;
    };
    const detail = axiosErr.response?.data?.error || axiosErr.response?.data?.detail;

    if (detail) {
      if (Array.isArray(detail)) {
        const firstErr = detail[0];
        errorMsg = firstErr?.msg
          ? `Validation Error: ${firstErr.loc?.slice(-1)[0] ?? 'field'} - ${firstErr.msg}`
          : JSON.stringify(detail);
      } else if (typeof detail === 'string') {
        errorMsg = detail;
      } else {
        errorMsg = JSON.stringify(detail);
      }
    } else if (axiosErr.message) {
      errorMsg = axiosErr.message;
    }
    setMessages((prev) => [
      ...prev,
      { id: generateId(), role: 'assistant', type: 'error', content: errorMsg },
    ]);
  };

  return {
    queryText,
    setQueryText,
    mode,
    setMode,
    messages,
    isLoading,
    handleSearch,
    executeEdit,
  };
}
