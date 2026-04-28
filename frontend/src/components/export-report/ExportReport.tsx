/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import { useState, useEffect } from 'react';
import { DownloadCloud, AlertTriangle, ClipboardList } from 'lucide-react';
import api from '@/services/api.service';
import { API_BASE } from '@/constants/config';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export interface QualityReport {
  status: string;
  score: number;
  readiness: string;
  metrics: {
    Rows: number;
    Columns: number;
    'Missing Value Ratio': string;
    'Duplicate Row Ratio': string;
  };
  imbalance_warnings: string[];
}

export interface ExportReportProps {
  sessionId: string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────────────────────── */

const getReadinessColor = (readiness: string): string => {
  if (readiness === 'Production Ready') {
    return 'bg-green-500/20 text-green-400 border-green-500/50';
  }
  if (readiness === 'Needs Review') {
    return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50';
  }
  return 'bg-red-500/20 text-red-400 border-red-500/50';
};

/* ─── Component ──────────────────────────────────────────────────────────────────────────── */

/**
 * ExportReport component that displays the final dataset quality assessment
 * and allows downloading the clean dataset.
 *
 * @param {ExportReportProps} props - Properties including the session identifier.
 * @returns {React.JSX.Element} The rendered report interface.
 */
export default function ExportReport({ sessionId }: ExportReportProps): React.JSX.Element {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get(`/api/report/${sessionId}`)
      .then((res) => setReport(res.data))
      .catch((err) => {
        const msg: string =
          err?.response?.data?.error ||
          err?.message ||
          'An unknown error occurred.';
        setError(msg);
        console.error('Failed to fetch report', err);
      })
      .finally(() => setIsLoading(false));
  }, [sessionId]);

  const handleDownload = () => {
    window.open(`${API_BASE}/api/download/${sessionId}?source=cleaned`, '_blank');
  };

  if (isLoading) {
    return (
      <div className="text-center p-12 text-neutral-500">
        Loading quality report...
      </div>
    );
  }

  if (!report) {
    const isCleaningMissing = error?.toLowerCase().includes('cleaned dataset not found') ||
      error?.toLowerCase().includes('no cleaned data');
    return (
      <div className="w-full bg-[#0A0A0A] border border-neutral-800 rounded-2xl p-12 shadow-2xl mt-6 flex flex-col items-center justify-center text-center">
        <div className="w-16 h-16 bg-red-500/10 rounded-2xl flex items-center justify-center mb-6">
          {isCleaningMissing
            ? <ClipboardList className="w-8 h-8 text-red-400" />
            : <AlertTriangle className="w-8 h-8 text-red-400" />}
        </div>
        <h3 className="text-xl font-bold text-white mb-2">
          {isCleaningMissing ? 'Cleaning Step Required' : 'Report Unavailable'}
        </h3>
        <p className="text-neutral-400 max-w-sm">
          {isCleaningMissing
            ? 'No cleaned dataset was found for this session. Please complete the Cleaning step before viewing the Quality Export report.'
            : (error ?? 'Failed to load report. Please try again.')}
        </p>
      </div>
    );
  }

  return (
    <div className="w-full bg-[#0A0A0A] border border-neutral-800 rounded-2xl p-8 shadow-2xl mt-6">
      <div className="flex justify-between items-start mb-8 border-b border-neutral-800/60 pb-6">
        <div>
          <h2 className="text-3xl font-black text-white flex items-center mb-2">
            Model-Readiness Score
          </h2>
          <p className="text-neutral-400">Final dataset quality assessment.</p>
        </div>
        <div className="text-right">
          <div className="text-5xl font-black text-blue-500">{report.score}/100</div>
          <div
            className={`mt-2 font-bold uppercase tracking-widest text-xs px-3 py-1 rounded-full border inline-block ${getReadinessColor(
              report.readiness
            )}`}
          >
            {report.readiness}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {Object.entries(report.metrics).map(([key, val]) => (
          <div key={key} className="bg-neutral-900 border border-neutral-800 p-4 rounded-xl">
            <div className="text-xs text-neutral-500 uppercase font-bold tracking-wider mb-1">
              {key}
            </div>
            <div className="text-xl font-mono text-white">{val}</div>
          </div>
        ))}
      </div>

      {report.imbalance_warnings && report.imbalance_warnings.length > 0 && (
        <div className="mb-8 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
          <h4 className="flex items-center font-bold text-yellow-500 mb-2">
            <AlertTriangle className="w-5 h-5 mr-2" /> Class Imbalance Warnings
          </h4>
          <ul className="list-disc pl-8 space-y-1 text-yellow-400/80 text-sm">
            {report.imbalance_warnings.map((warn, i) => (
              <li key={i}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-center mt-8 pt-4 border-t border-neutral-800/60">
        <button
          onClick={handleDownload}
          className="flex items-center px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-colors shadow-lg hover:shadow-blue-500/20"
        >
          <DownloadCloud className="w-6 h-6 mr-3" />
          Export Production-Ready Dataset
        </button>
      </div>
    </div>
  );
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */
