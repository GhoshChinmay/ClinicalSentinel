"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, Loader2, ShieldCheck, Trash2, Edit, BarChart, Brain, Terminal, AlertOctagon, ArrowRight, FileCheck, Zap } from "lucide-react";
import { AxiosError } from "axios";
import api from "@/services/api.service";
import type { UploadResponse, InsightsDashboardResponse } from "@/types/api";

interface SampleDataset {
  filename: string;
  name: string;
  rows: number;
  anomalies: number;
  description: string;
  icon: string;
}

// ── Components ──
import HeroLanding from "@/components/landing/HeroLanding";
import Detection from "@/components/detection";
import Clean from "@/components/clean";
import ReviewEdit from "@/components/review-edit";
import Visualizer from "@/components/visualizer";
import Insights from "@/components/insights";
import Query from "@/components/query";
import Compare from "@/components/compare";
import ExportReport from "@/components/export-report";
import PIIModal from "@/components/pii-modal";
import type { PIIFinding } from "@/components/pii-modal/PIIModal";

type PipelineStep = 'upload' | 'detect' | 'insights' | 'clean' | 'compare' | 'edit' | 'visualize' | 'query' | 'report';

export default function Home() {
  // ── State Management ──
  const [currentStep, setCurrentStep] = useState<PipelineStep>('upload');
  const [isUploading, setIsUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [cachedInsights, setCachedInsights] = useState<InsightsDashboardResponse | null>(null);
  const [recommendedMethod, setRecommendedMethod] = useState<string>('quarantine');
  const [cleaningRationale, setCleaningRationale] = useState<string>('');
  const [contractErrors, setContractErrors] = useState<string[] | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  /* uploadError is displayed below the upload portal */
  const [piiFindings, setPiiFindings] = useState<PIIFinding[]>([]);
  const [showPIIModal, setShowPIIModal] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [samples, setSamples] = useState<SampleDataset[]>([]);

  useEffect(() => {
    api.get('/api/samples').then(res => setSamples(res.data.samples)).catch(console.error);
  }, []);

  // ── File Handlers ──
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) await processUpload(e.target.files[0]);
  };

  const processUpload = async (uploadFile: File) => {
    setIsUploading(true); setUploadError(null); setContractErrors(null);
    const formData = new FormData(); formData.append("file", uploadFile);
    try {
      const response = await api.post<UploadResponse>("/api/upload/", formData);
      const sid = response.data.session_id; setSessionId(sid);
      setRecommendedMethod(response.data.recommended_cleaning || 'quarantine');
      setCleaningRationale(response.data.cleaning_rationale || '');
      try {
        const piiRes = await api.get(`/api/pii-scan/${sid}`);
        if (piiRes.data.pii_detected) { setPiiFindings(piiRes.data.findings); setShowPIIModal(true); }
        else { setCurrentStep('detect'); }
      } catch { setCurrentStep('detect'); }
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ error?: string; errors?: string[] }>;
      if (axiosErr.response?.status === 400 && axiosErr.response?.data?.errors?.length) setContractErrors(axiosErr.response.data.errors);
      else setUploadError(axiosErr.response?.data?.error || "Unknown error occurred");
    } finally { setIsUploading(false); }
  };

  const loadSample = async (filename: string) => {
    setIsUploading(true); setUploadError(null); setContractErrors(null);
    try {
      const response = await api.post<UploadResponse>(`/api/load-sample/${filename}`);
      const sid = response.data.session_id; setSessionId(sid);
      setCleaningRationale(response.data.cleaning_rationale || '');
      try {
        const piiRes = await api.get(`/api/pii-scan/${sid}`);
        if (piiRes.data.pii_detected) { setPiiFindings(piiRes.data.findings); setShowPIIModal(true); }
        else { setCurrentStep('detect'); }
      } catch { setCurrentStep('detect'); }
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ error?: string; errors?: string[] }>;
      if (axiosErr.response?.status === 400 && axiosErr.response?.data?.errors?.length) setContractErrors(axiosErr.response.data.errors);
      else setUploadError(axiosErr.response?.data?.error || "Unknown error occurred");
    } finally { setIsUploading(false); }
  };

  const renderNav = () => {
    if (currentStep === 'upload') return null;
    const steps = [
      { id: 'detect', icon: <ShieldCheck size={16} />, label: 'Detection' },
      { id: 'insights', icon: <Brain size={16} />, label: 'Insights' },
      { id: 'clean', icon: <Trash2 size={16} />, label: 'Cleaning' },
      { id: 'compare', icon: <ArrowRight size={16} />, label: 'Compare' },
      { id: 'edit', icon: <Edit size={16} />, label: 'Edit' },
      { id: 'visualize', icon: <BarChart size={16} />, label: 'Visualizer' },
      { id: 'query', icon: <Terminal size={16} />, label: 'Query' },
      { id: 'report', icon: <FileCheck size={16} />, label: 'Quality Export' }
    ];
    return (
      <nav className="border-b border-white/5 bg-black/20 backdrop-blur-xl sticky top-0 z-50 p-4 flex justify-center space-x-2 md:space-x-4 overflow-x-auto">
        {steps.map((step) => (
          <button key={step.id} onClick={() => setCurrentStep(step.id as PipelineStep)} disabled={!sessionId}
            className={`flex items-center px-4 py-2 rounded-xl text-xs md:text-sm font-bold transition-all whitespace-nowrap ${currentStep === step.id ? 'bg-white text-black shadow-lg' : 'text-neutral-500 hover:text-white hover:bg-neutral-900'}`}
          >
            <span className="mr-2">{step.icon}</span>{step.label}
          </button>
        ))}
      </nav>
    );
  };

  return (
    <main className="min-h-screen bg-black text-white flex flex-col font-sans selection:bg-purple-500 selection:text-white overflow-clip">

      {/* ── Fixed Header for Landing Page ── */}
      <AnimatePresence>
        {currentStep === 'upload' && (
          <motion.header
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed top-0 left-0 w-full p-6 z-50 flex justify-between items-center mix-blend-difference pointer-events-none"
          >
            <div className="text-xl font-black tracking-tighter">DATA<span className="text-purple-500">SENTINEL</span></div>
          </motion.header>
        )}
      </AnimatePresence>

      {renderNav()}

      {/* ── Main Content Area ── */}
      <AnimatePresence mode="wait">
        {currentStep === 'upload' ? (
          <motion.div
            key="landing"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.5 } }} // Smooth fade out gives GSAP time to unmount
            className="w-full"
          >
            {/* Act 1 & 2 */}
            <HeroLanding />

            {/* ── Act 3: The Engine (Sticky Features) ── */}
            <div className="relative w-full bg-black text-white py-32 px-6 md:px-12 lg:px-24 max-w-[1400px] mx-auto flex flex-col md:flex-row items-start gap-12 lg:gap-24 border-t border-white/5">
              <div className="md:w-1/3 sticky top-32 pt-10">
                <h2 className="text-sm font-bold uppercase tracking-[0.2em] text-purple-500 mb-4 flex items-center gap-2">
                  <Brain className="w-4 h-4" /> The Architecture
                </h2>
                <h3 className="text-4xl md:text-5xl lg:text-6xl font-black tracking-tight leading-[1.1] mb-6">
                  Built for the <br /> Age of AI.
                </h3>
                <p className="text-neutral-400 text-lg md:text-xl font-medium leading-relaxed">
                  Legacy tools buckle under modern data volume. DataSentinel fuses deterministic logic with Groq-accelerated AI to clean data at the speed of thought.
                </p>
              </div>
              <div className="md:w-2/3 flex flex-col gap-8 md:gap-12 pt-10 md:pt-32 pb-32">
                <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="bg-neutral-900/40 border border-white/5 p-8 md:p-12 rounded-[2rem] hover:bg-neutral-900/60 hover:border-purple-500/30 transition-colors group">
                  <div className="w-14 h-14 bg-rose-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><ShieldCheck className="w-7 h-7 text-rose-500" /></div>
                  <h4 className="text-3xl font-bold mb-4 tracking-tight">Zero-Leak PII Vault</h4>
                  <p className="text-neutral-400 text-lg leading-relaxed">Before a single byte is analyzed, our local edge-scanner identifies and cryptographically vaults personal identities. Your sensitive data never hits the cloud.</p>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="bg-neutral-900/40 border border-white/5 p-8 md:p-12 rounded-[2rem] hover:bg-neutral-900/60 hover:border-purple-500/30 transition-colors group">
                  <div className="w-14 h-14 bg-emerald-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><Terminal className="w-7 h-7 text-emerald-500" /></div>
                  <h4 className="text-3xl font-bold mb-4 tracking-tight">Neuro-Symbolic Logic</h4>
                  <p className="text-neutral-400 text-lg leading-relaxed">We don&apos;t just guess. DataSentinel combines strict, dynamic mathematical rules with semantic AI evaluation to automatically reject impossible realities in your dataset.</p>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="bg-neutral-900/40 border border-white/5 p-8 md:p-12 rounded-[2rem] hover:bg-neutral-900/60 hover:border-purple-500/30 transition-colors group">
                  <div className="w-14 h-14 bg-cyan-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><Zap className="w-7 h-7 text-cyan-500" /></div>
                  <h4 className="text-3xl font-bold mb-4 tracking-tight">Groq LPU Acceleration</h4>
                  <p className="text-neutral-400 text-lg leading-relaxed">Powered by Llama 3.3 70B running on Groq&apos;s Language Processing Units. Generate complex SQL queries, statistical profiles, and narrative insights in literal milliseconds.</p>
                </motion.div>
              </div>
            </div>

            {/* ── Act 4: The Upload Portal ── */}
            <div className="relative w-full min-h-screen bg-black flex flex-col items-center justify-center py-24 px-4 border-t border-white/5">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/20 via-black to-black"></div>
              <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="w-full max-w-2xl flex flex-col items-center justify-center bg-neutral-900/40 backdrop-blur-3xl p-10 rounded-[2.5rem] border border-white/10 shadow-[0_0_100px_rgba(168,85,247,0.15)] relative z-10">
                <h1 className="text-4xl md:text-5xl font-black tracking-tighter mb-8 text-center">Flawless Data. <br /><span className="text-purple-500">Ready for Production.</span></h1>
                <div className="w-full border border-dashed border-white/20 bg-white/[0.02] hover:bg-white/[0.05] rounded-[2rem] p-10 transition-all duration-300 flex flex-col items-center justify-center cursor-pointer hover:border-purple-500/50 group" onClick={() => fileInputRef.current?.click()}>
                  <input type="file" className="hidden" accept=".csv,.xlsx,.xls,.json" ref={fileInputRef} onChange={handleFileChange} />
                  {isUploading ? (
                    <div className="flex flex-col items-center text-purple-400"><Loader2 className="w-10 h-10 animate-spin mb-4" /><p className="font-medium tracking-wide">Initializing Pipeline...</p></div>
                  ) : (
                    <div className="flex flex-col items-center"><div className="p-4 bg-white/5 rounded-full mb-4 group-hover:bg-purple-500/20 transition-colors"><UploadCloud className="w-8 h-8 text-neutral-300 group-hover:text-purple-400 transition-colors" /></div><p className="text-xl font-medium mb-2 tracking-tight">Secure Upload</p><p className="text-sm text-neutral-500">Drop your CSV, JSON, or Excel file here.</p></div>
                  )}
                </div>
                {samples.length > 0 && (
                  <div className="w-full mt-8 grid grid-cols-1 md:grid-cols-2 gap-3">
                    {samples.map((sample) => (
                      <div key={sample.filename} className="bg-white/[0.02] border border-white/5 p-4 rounded-2xl cursor-pointer hover:bg-white/[0.06] hover:border-white/10 transition-all flex items-center justify-between group/card" onClick={() => loadSample(sample.filename)}>
                        <div className="flex items-center gap-3"><span className="text-2xl">{sample.icon}</span><h4 className="font-medium text-sm text-neutral-200">{sample.name}</h4></div>
                        <ArrowRight size={14} className="text-neutral-600 group-hover/card:text-purple-500" />
                      </div>
                    ))}
                  </div>
                )}
                {uploadError && (
                  <div className="w-full mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-2xl text-center">
                    <p className="text-red-400 text-sm font-medium">{uploadError}</p>
                  </div>
                )}
              </motion.div>
            </div>
          </motion.div>
        ) : (
          // ── DASHBOARD LOGIC (Intact) ──
          <motion.div
            key="dashboard"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex-1 flex flex-col items-center p-6 w-full max-w-6xl mx-auto relative z-10"
          >
            <AnimatePresence mode="wait">
              {currentStep === 'detect' && (
                <motion.div key="detect" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  <div className="mb-6"><h2 className="text-2xl font-semibold mb-1">Anomaly Detection Engine</h2><p className="text-neutral-400">Review flagged shards.</p></div>
                  {sessionId && <Detection key={sessionId} sessionId={sessionId} />}
                  <div className="mt-8 flex justify-end"><button onClick={() => setCurrentStep('insights')} className="px-6 py-3 bg-white text-black font-medium rounded-xl shadow-lg hover:bg-neutral-200 transition-colors">Proceed &rarr;</button></div>
                </motion.div>
              )}
              {currentStep === 'insights' && (
                <motion.div key="insights" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <Insights sessionId={sessionId} cachedInsights={cachedInsights} onInsightsLoaded={setCachedInsights} />}
                  <div className="mt-8 flex justify-end"><button onClick={() => setCurrentStep('clean')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors">Next &rarr;</button></div>
                </motion.div>
              )}
              {currentStep === 'clean' && (
                <motion.div key="clean" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <Clean key={sessionId} sessionId={sessionId} onComplete={() => setCurrentStep('compare')} recommendedMethod={recommendedMethod} cleaningRationale={cleaningRationale} />}
                </motion.div>
              )}
              {currentStep === 'compare' && (
                <motion.div key="compare" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <Compare key={sessionId} sessionId={sessionId} />}
                  <div className="mt-8 flex justify-end"><button onClick={() => setCurrentStep('edit')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors">Review &rarr;</button></div>
                </motion.div>
              )}
              {currentStep === 'edit' && (
                <motion.div key="edit" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <ReviewEdit key={sessionId} sessionId={sessionId} />}
                </motion.div>
              )}
              {currentStep === 'visualize' && (
                <motion.div key="viz" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <Visualizer key={sessionId} sessionId={sessionId} />}
                </motion.div>
              )}
              {currentStep === 'query' && (
                <motion.div key="query" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <Query key={sessionId} sessionId={sessionId} />}
                  <div className="mt-8 flex justify-end"><button onClick={() => setCurrentStep('report')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors">Report &rarr;</button></div>
                </motion.div>
              )}
              {currentStep === 'report' && (
                <motion.div key="report" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <ExportReport key={sessionId} sessionId={sessionId} />}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* MODALS */}
      <AnimatePresence>
        {contractErrors && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-neutral-900 border border-red-500/30 rounded-3xl p-6 max-w-lg shadow-2xl">
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2"><AlertOctagon className="text-red-500" /> Data Contract Violation</h2>
              <ul className="space-y-2 mb-6">{contractErrors.map((e, i) => <li key={i} className="text-neutral-400 text-sm">{e}</li>)}</ul>
              <button onClick={() => setContractErrors(null)} className="w-full py-3 bg-neutral-800 hover:bg-neutral-700 transition-colors text-white font-bold rounded-xl">Acknowledge</button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showPIIModal && piiFindings.length > 0 && sessionId && (
          <PIIModal sessionId={sessionId} findings={piiFindings} onDismiss={() => { setShowPIIModal(false); setCurrentStep('detect'); }} onPseudonymised={() => { setShowPIIModal(false); setCurrentStep('detect'); }} />
        )}
      </AnimatePresence>
    </main>
  );
}