import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { DownloadCloud, AlertTriangle } from 'lucide-react';

interface QualityReport {
  status: string;
  score: number;
  readiness: string;
  metrics: {
    Rows: number;
    Columns: number;
    "Missing Value Ratio": string;
    "Duplicate Row Ratio": string;
  };
  imbalance_warnings: string[];
}

export default function ExportReport({ sessionId }: { sessionId: string }) {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/api/report/${sessionId}`)
      .then(res => setReport(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId]);

  const handleDownload = () => {
    window.open(`${api.defaults.baseURL || 'http://127.0.0.1:8000'}/api/download/${sessionId}?source=cleaned`, '_blank');
  };

  if (loading) return <div className="text-center p-12 text-neutral-500">Loading quality report...</div>;
  if (!report) return <div className="text-center p-12 text-red-500">Failed to load report.</div>;

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
          <div className={`mt-2 font-bold uppercase tracking-widest text-xs px-3 py-1 rounded-full border inline-block
            ${report.readiness === 'Production Ready' ? 'bg-green-500/20 text-green-400 border-green-500/50' : 
              report.readiness === 'Needs Review' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50' : 
              'bg-red-500/20 text-red-400 border-red-500/50'}`}>
            {report.readiness}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {Object.entries(report.metrics).map(([key, val]) => (
          <div key={key} className="bg-neutral-900 border border-neutral-800 p-4 rounded-xl">
            <div className="text-xs text-neutral-500 uppercase font-bold tracking-wider mb-1">{key}</div>
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
