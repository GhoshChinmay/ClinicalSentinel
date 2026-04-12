/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, Lock, X, Eye } from 'lucide-react';
import api from '@/services/api.service';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export interface PIIFinding {
  column: string;
  pii_type: string;
  confidence: 'high' | 'medium';
  sample_value: string | null;
}

export interface PIIModalProps {
  sessionId: string;
  findings: PIIFinding[];
  onDismiss: () => void;
  onPseudonymised: (columns: string[]) => void;
}

/* ─── Helpers ────────────────────────────────────────────────────────────────────────────── */

const getInitialSelected = (findings: PIIFinding[]): Set<string> => {
  return new Set(
    findings.filter((f) => f.confidence === 'high').map((f) => f.column)
  );
};

/* ─── Component ──────────────────────────────────────────────────────────────────────────── */

/**
 * PIIModal component for handling Personally Identifiable Information.
 * Detects PII columns and allows users to pseudonymise them before proceeding.
 *
 * @param {PIIModalProps} props - The properties for the modal.
 * @returns {JSX.Element} The rendered modal component.
 */
export default function PIIModal({
  sessionId,
  findings,
  onDismiss,
  onPseudonymised,
}: PIIModalProps): JSX.Element {
  const [selected, setSelected] = useState<Set<string>>(getInitialSelected(findings));
  const [isLoading, setIsLoading] = useState(false);
  const [isDone, setIsDone] = useState(false);

  const toggleColumnSelection = (col: string) => {
    const nextSelected = new Set(selected);
    if (nextSelected.has(col)) {
      nextSelected.delete(col);
    } else {
      nextSelected.add(col);
    }
    setSelected(nextSelected);
  };

  const handlePseudonymise = async () => {
    if (selected.size === 0) {
      onDismiss();
      return;
    }
    
    setIsLoading(true);
    try {
      await api.post(`/api/pseudonymise/${sessionId}`, Array.from(selected));
      setIsDone(true);
      setTimeout(() => {
        onPseudonymised(Array.from(selected));
      }, 1500);
    } catch (error) {
      console.error('Failed to pseudonymise data', error);
      setIsLoading(false);
    }
  };

  if (isDone) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-[#080808] border border-neutral-800 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden py-8 text-center"
        >
          <ShieldCheck className="w-16 h-16 text-emerald-400 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-white mb-2">Pseudonymisation Applied</h3>
          <p className="text-neutral-400 text-sm">
            Salted SHA-256 hashing applied. Original values are securely protected.
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="bg-[#080808] border border-neutral-800 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden"
      >
        <div className="bg-amber-500/10 border-b border-amber-500/20 p-6 flex items-start justify-between">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-amber-500/20 rounded-xl flex items-center justify-center mr-4 shrink-0">
              <Eye className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">PII Detected</h2>
              <p className="text-amber-400/80 text-xs mt-0.5">GDPR Art. 25 compliance alert</p>
            </div>
          </div>
          <button
            onClick={onDismiss}
            className="text-neutral-600 hover:text-white transition-colors ml-4"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          <p className="text-sm text-neutral-400 mb-4 leading-relaxed">
            The following columns appear to contain personally identifiable information.
            Select columns to pseudonymise (hash) before proceeding.
          </p>

          <div className="space-y-2 mb-6 max-h-56 overflow-y-auto pr-1 custom-scrollbar">
            {findings.map((f) => (
              <div
                key={f.column}
                onClick={() => toggleColumnSelection(f.column)}
                className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                  selected.has(f.column)
                    ? 'bg-amber-500/10 border-amber-500/40'
                    : 'bg-neutral-900 border-neutral-800'
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        f.confidence === 'high'
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-amber-500/20 text-amber-400'
                      }`}
                    >
                      {f.confidence.toUpperCase()}
                    </span>
                    <span className="text-sm font-mono text-white">{f.column}</span>
                  </div>
                  <p className="text-[11px] text-neutral-500 mt-0.5">
                    {f.pii_type}
                    {f.sample_value && (
                      <span className="ml-2 text-neutral-600">e.g. "{f.sample_value}"</span>
                    )}
                  </p>
                </div>
                <div
                  className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 transition-all ${
                    selected.has(f.column)
                      ? 'bg-amber-500 border-amber-500 text-black'
                      : 'border-neutral-700'
                  }`}
                >
                  {selected.has(f.column) && <span className="text-[10px] font-black">✓</span>}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-2 mb-4 p-3 bg-blue-500/5 border border-blue-500/20 rounded-xl">
            <Lock className="w-4 h-4 text-blue-400 shrink-0" />
            <p className="text-[11px] text-blue-400/80 leading-relaxed">
              Pseudonymisation happens entirely on your device. No data leaves this instance.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={onDismiss}
              className="flex-1 py-3 text-sm font-medium text-neutral-400 hover:text-white bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 rounded-xl transition-all"
            >
              Skip
            </button>
            <button
              onClick={handlePseudonymise}
              disabled={isLoading}
              className="flex-1 py-3 text-sm font-bold text-black bg-amber-400 hover:bg-amber-300 rounded-xl transition-all disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <span className="animate-spin">◌</span>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" /> Hash {selected.size} Column
                  {selected.size !== 1 ? 's' : ''}
                </>
              )}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */
