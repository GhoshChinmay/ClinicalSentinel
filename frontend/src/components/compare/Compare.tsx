/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { ArrowRight, CheckCircle, Loader2, Info } from 'lucide-react';
import { useCompare } from '@/hooks/use-compare';

/* ─── Types & Constants ──────────────────────────────────────────────────────────────────── */

export interface CompareProps {
  sessionId: string;
}

const IGNORE_KEYS = [
  'is_anomaly',
  'AI_Reason',
  'Threat_Score',
];

/* ─── Helpers ────────────────────────────────────────────────────────────────────────────── */

const isKeyChanged = (key: string, origRow: any, cleanRow: any): boolean => {
  if (IGNORE_KEYS.includes(key)) return false;
  if (
    key.endsWith('_freq') ||
    key.endsWith('_length') ||
    key.endsWith('_digit_ratio') ||
    key.endsWith('_upper_ratio') ||
    key.endsWith('_special_ratio')
  ) {
    return false;
  }
  if (key.startsWith('nlp_pc')) return false;
  if (key === 'velocity_24h_sum' || key === 'velocity_1h_count') return false;
  return origRow[key] !== cleanRow[key];
};

const formatValue = (val: any): string => {
  if (val === null) return 'NULL';
  if (typeof val === 'number') return Number(val).toFixed(2);
  return String(val);
};

/* ─── Components ─────────────────────────────────────────────────────────────────────────── */

/**
 * Compare component to visualize the modifications made to the dataset
 * during the sanitization step.
 *
 * @param {CompareProps} props - Properties including the session identifier.
 * @returns {JSX.Element | null} The comparison component.
 */
export default function Compare({ sessionId }: CompareProps): JSX.Element | null {
  const { data, isLoading, errorMsg } = useCompare(sessionId);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-neutral-400">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-4" />
        <p>Analyzing dataset modifications...</p>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="text-red-500 bg-red-500/10 p-4 rounded-xl border border-red-500/20">
        {errorMsg}
      </div>
    );
  }

  if (!data) return null;

  if (data.is_dropped) {
    return (
      <div className="bg-green-500/10 border border-green-500/30 rounded-2xl p-10 flex flex-col items-center text-center">
        <CheckCircle className="w-16 h-16 text-green-500 mb-4" />
        <h3 className="text-2xl font-bold text-white mb-2">Anomalies Successfully Removed</h3>
        <p className="text-neutral-400 max-w-md">
          You chose to drop or quarantine the anomalous rows. The dataset has been cleanly reduced,
          so there are no inline modifications to compare.
        </p>
      </div>
    );
  }

  if (data.count === 0) {
    return (
      <p className="text-neutral-500 text-center py-10">
        No modifications found. The dataset was already clean.
      </p>
    );
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between bg-blue-500/10 border border-blue-500/20 p-4 rounded-xl">
        <div className="flex items-center text-blue-400">
          <Info className="w-5 h-5 mr-3" />
          <span className="font-medium">
            Showing top {data.original.length} repaired rows out of {data.count} total modifications.
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {data.original.map((origRow, i) => {
          const cleanRow = data.cleaned[i];
          if (!cleanRow) return null;

          const changedKeys = Object.keys(origRow).filter((k) =>
            isKeyChanged(k, origRow, cleanRow)
          );

          return (
            <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-lg overflow-hidden relative">
              <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
              <h4 className="text-sm font-bold text-neutral-500 mb-4 uppercase tracking-wider">
                Repaired Row #{i + 1}
              </h4>

              {changedKeys.length > 0 ? (
                <div className="space-y-4">
                  {changedKeys.map((key) => (
                    <div key={key} className="flex flex-col md:flex-row md:items-center bg-black/40 rounded-xl p-4 border border-neutral-800/50">
                      <span className="text-neutral-400 font-medium w-48 shrink-0 mb-2 md:mb-0">
                        {key}
                      </span>
                      <div className="flex items-center flex-1 min-w-0">
                        <div className="bg-red-500/10 text-red-400 px-3 py-2 rounded-lg border border-red-500/20 flex-1 truncate line-through opacity-70">
                          {formatValue(origRow[key])}
                        </div>
                        <ArrowRight className="w-5 h-5 text-neutral-600 mx-4 shrink-0" />
                        <div className="bg-green-500/10 text-green-400 font-bold px-3 py-2 rounded-lg border border-green-500/20 flex-1 truncate shadow-[0_0_15px_rgba(34,197,94,0.15)]">
                          {formatValue(cleanRow[key])}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-neutral-500 italic">No numeric values were altered in this row.</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */
