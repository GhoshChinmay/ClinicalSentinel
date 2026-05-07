"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Scale, BookOpen, CheckCircle, ShieldAlert, RefreshCw } from "lucide-react";
import api from "@/services/api.service";

interface Props {
  sessionId: string;
}

export default function RegRagCompliance({ sessionId }: Props) {
  const [initLoading, setInitLoading] = useState(false);
  const [evalLoading, setEvalLoading] = useState(false);
  const [initStatus, setInitStatus] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const [investigatorId, setInvestigatorId] = useState("");
  const [anomalyDetails, setAnomalyDetails] = useState('{"layer1_benford": 80, "layer2_burst": 90}');

  const initKB = async () => {
    setInitLoading(true);
    setInitStatus(null);
    try {
      const res = await api.post(`/api/clinical/reg-rag/init`);
      setInitStatus(res.data.message);
    } catch (e: any) {
      setInitStatus("Failed to initialize Knowledge Base.");
    } finally {
      setInitLoading(false);
    }
  };

  const evaluate = async () => {
    if (!investigatorId) return;
    setEvalLoading(true);
    try {
      const res = await api.post(`/api/clinical/reg-rag/evaluate`, {
        investigator_id: investigatorId,
        anomaly_details: JSON.parse(anomalyDetails)
      });
      setResult(res.data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setEvalLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-black text-white mb-1">
          RegRAG Compliance <span className="text-purple-400">F4</span>
        </h2>
        <p className="text-neutral-500 text-sm">
          Retrieval-Augmented Generation against ICH E6(R3), 21 CFR Part 11, and DPDP Act.
        </p>
      </div>

      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 flex items-center justify-between">
        <div>
          <h3 className="font-bold text-white text-sm mb-1 flex items-center gap-2"><BookOpen size={14} className="text-purple-400"/> Regulatory Knowledge Base</h3>
          <p className="text-xs text-neutral-500">Initialize the vector DB with regulatory text before running evaluations.</p>
          {initStatus && <p className="text-xs text-emerald-400 mt-2">{initStatus}</p>}
        </div>
        <button onClick={initKB} disabled={initLoading} className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white text-sm font-medium rounded-xl flex items-center gap-2 transition-colors">
          {initLoading ? <RefreshCw size={14} className="animate-spin" /> : <Scale size={14} />} Initialize KB
        </button>
      </div>

      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 space-y-4">
        <h3 className="font-bold text-white text-sm mb-2">Test Compliance Evaluation</h3>
        <div className="flex gap-4">
           <div className="flex-1">
             <label className="text-xs text-neutral-500 mb-1.5 block">Investigator ID</label>
             <input type="text" value={investigatorId} onChange={e => setInvestigatorId(e.target.value)} className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none" />
           </div>
           <div className="flex-[2]">
             <label className="text-xs text-neutral-500 mb-1.5 block">Anomaly Details (JSON)</label>
             <input type="text" value={anomalyDetails} onChange={e => setAnomalyDetails(e.target.value)} className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none font-mono" />
           </div>
           <div className="flex items-end">
             <button onClick={evaluate} disabled={evalLoading || !investigatorId} className="px-6 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl disabled:opacity-40 transition-colors flex items-center gap-2">
               {evalLoading ? <RefreshCw size={14} className="animate-spin" /> : <ShieldAlert size={14} />} Evaluate
             </button>
           </div>
        </div>

        {result && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 p-4 bg-neutral-900 border border-purple-500/30 rounded-xl">
             <h4 className="font-bold text-sm text-purple-400 mb-2">Regulatory Verdict</h4>
             <p className="text-sm text-neutral-300 leading-relaxed">{result.regulatory_verdict}</p>
             
             <h4 className="font-bold text-sm text-neutral-400 mt-4 mb-2">Citations</h4>
             <ul className="list-disc pl-4 space-y-1">
               {result.citations?.map((c: string, i: number) => (
                 <li key={i} className="text-xs text-neutral-500">{c}</li>
               ))}
             </ul>
          </motion.div>
        )}
      </div>
    </div>
  );
}
