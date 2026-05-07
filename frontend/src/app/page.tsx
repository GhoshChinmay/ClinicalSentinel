"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  UploadCloud, ShieldCheck, Trash2, Edit, BarChart, Brain,
  Terminal, AlertOctagon, ArrowRight, FileCheck, Zap, CheckCircle,
  Microscope, Fingerprint, Scale, Activity
} from "lucide-react";
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
import NeuralCore from "@/components/landing/NeuralCore";
import AmbientAurora from "@/components/landing/AmbientAurora";
import Detection from "@/components/detection";
import Clean from "@/components/clean";
import ReviewEdit from "@/components/review-edit";
import Visualizer from "@/components/visualizer";
import Insights from "@/components/insights";
import Query from "@/components/query";
import Compare from "@/components/compare";
import ExportReport from "@/components/export-report";
import PIIModal from "@/components/pii-modal";
import FRIDashboard from "@/components/fri-dashboard/FRIDashboard"; // NEW: Forensic Audit Dashboard
import type { PIIFinding } from "@/components/pii-modal/PIIModal";

// NEW: Added 'forensic' to PipelineStep
type PipelineStep = 'upload' | 'detect' | 'forensic' | 'insights' | 'clean' | 'compare' | 'edit' | 'visualize' | 'query' | 'report';

// ── Custom High-Tech Loader Animation ──
const QuantumLoader = () => (
  <div className="relative w-5 h-5 flex items-center justify-center shrink-0">
    <motion.div
      className="absolute inset-0 border-2 border-cyan-500/20 border-t-cyan-400 rounded-full"
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    />
    <motion.div
      className="absolute inset-[3px] border-2 border-purple-500/20 border-b-purple-400 rounded-full"
      animate={{ rotate: -360 }}
      transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
    />
    <div className="w-1 h-1 bg-cyan-300 rounded-full animate-pulse shadow-[0_0_8px_#67e8f9]" />
  </div>
);

export default function Home() {
  // ── State Management ──
  const [currentStep, setCurrentStep] = useState<PipelineStep>('upload');
  const [isUploading, setIsUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // NEW: State to hold columns for the FRI Dashboard mapping tool
  const [columns, setColumns] = useState<string[]>([]);

  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadedBytes, setUploadedBytes] = useState<{ loaded: number, total: number } | null>(null);

  const [processingStatus, setProcessingStatus] = useState<string>("");
  const [statusHistory, setStatusHistory] = useState<string[]>([]);

  const [cachedInsights, setCachedInsights] = useState<InsightsDashboardResponse | null>(null);
  const [recommendedMethod, setRecommendedMethod] = useState<string>('quarantine');
  const [cleaningRationale, setCleaningRationale] = useState<string>('');
  const [contractErrors, setContractErrors] = useState<string[] | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [piiFindings, setPiiFindings] = useState<PIIFinding[]>([]);
  const [showPIIModal, setShowPIIModal] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [samples, setSamples] = useState<SampleDataset[]>([]);

  useEffect(() => {
    api.get('/api/samples').then(res => setSamples(res.data.samples)).catch(console.error);
  }, []);

  const formatMB = (bytes: number) => (bytes / (1024 * 1024)).toFixed(1);

  // ── Variable-Speed Backend Simulation ──
  const simulateBackendProcessing = (sid: string) => {
    const steps = [
      { text: "Establishing secure WebSocket connection...", delay: 600 },
      { text: "Allocating secure memory buffers...", delay: 800 },
      { text: "Ingesting dataset via Polars engine...", delay: 2500 },
      { text: "Cryptographically vaulting PII signatures...", delay: 2000 },
      { text: "Running 7-Layer Forensic anomaly detection...", delay: 3500 }, // Updated text
      { text: "Compiling neuro-symbolic logic gates...", delay: 1500 },
      { text: "PIPELINE_COMPLETE", delay: 0 }
    ];

    let stepIndex = 0;
    setProcessingStatus(steps[0].text);

    const processNextStep = () => {
      stepIndex++;
      if (stepIndex >= steps.length) {
        checkPiiAndProceed(sid);
        return;
      }

      const currentStep = steps[stepIndex];

      if (currentStep.text !== "PIPELINE_COMPLETE") {
        setStatusHistory(prev => {
          const newHistory = [...prev, steps[stepIndex - 1].text];
          return newHistory.slice(-3); // Keep only the last 3 messages
        });
        setProcessingStatus(currentStep.text);
        setTimeout(processNextStep, currentStep.delay);
      } else {
        checkPiiAndProceed(sid);
      }
    };

    setTimeout(processNextStep, steps[0].delay);
  };

  const checkPiiAndProceed = async (sid: string) => {
    try {
      // Fetch columns so the FRIDashboard knows what to map
      const dataRes = await api.get(`/api/data/${sid}?limit=1`);
      if (dataRes.data?.data?.[0]) {
        setColumns(Object.keys(dataRes.data.data[0]));
      }

      const piiRes = await api.get(`/api/pii-scan/${sid}`);
      if (piiRes.data.pii_detected) {
        setPiiFindings(piiRes.data.findings);
        setShowPIIModal(true);
      }
      else { setCurrentStep('detect'); }
    } catch {
      setCurrentStep('detect');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
      setStatusHistory([]);
    }
  };

  // ── File Handlers ──
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) await processUpload(e.target.files[0]);
  };

  const processUpload = async (uploadFile: File) => {
    setIsUploading(true); setUploadError(null); setContractErrors(null);
    setUploadProgress(0); setUploadedBytes(null); setStatusHistory([]);
    setProcessingStatus(""); // Reset terminal text

    const formData = new FormData(); formData.append("file", uploadFile);

    try {
      const response = await api.post<UploadResponse>("/api/upload/", formData, {
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(percentCompleted);
            setUploadedBytes({ loaded: progressEvent.loaded, total: progressEvent.total });

            // BUG FIX: Inject immediate waiting message at 100%
            if (percentCompleted === 100) {
              setProcessingStatus("File transferred. Server digesting dataset payload...");
            }
          }
        },
      });

      const sid = response.data.session_id; setSessionId(sid);
      setRecommendedMethod(response.data.recommended_cleaning || 'quarantine');
      setCleaningRationale(response.data.cleaning_rationale || '');

      simulateBackendProcessing(sid);

    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ error?: string; errors?: string[] }>;
      if (axiosErr.response?.status === 400 && axiosErr.response?.data?.errors?.length) setContractErrors(axiosErr.response.data.errors);
      else setUploadError(axiosErr.response?.data?.error || "Unknown error occurred");
      setIsUploading(false); setUploadProgress(0);
    }
  };

  const loadSample = async (filename: string) => {
    setIsUploading(true); setUploadError(null); setContractErrors(null); setStatusHistory([]);
    setUploadProgress(100);
    setProcessingStatus("File transferred. Server digesting dataset payload...");

    try {
      const response = await api.post<UploadResponse>(`/api/load-sample/${filename}`);
      const sid = response.data.session_id; setSessionId(sid);
      setCleaningRationale(response.data.cleaning_rationale || '');

      simulateBackendProcessing(sid);

    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ error?: string; errors?: string[] }>;
      if (axiosErr.response?.status === 400 && axiosErr.response?.data?.errors?.length) setContractErrors(axiosErr.response.data.errors);
      else setUploadError(axiosErr.response?.data?.error || "Unknown error occurred");
      setIsUploading(false); setUploadProgress(0);
    }
  };

  const renderNav = () => {
    if (currentStep === 'upload') return null;
    const steps = [
      { id: 'detect', icon: <ShieldCheck size={16} />, label: 'Detection' },
      { id: 'forensic', icon: <Microscope size={16} />, label: 'Forensic Audit' }, // NEW TAB
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

  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (uploadProgress / 100) * circumference;

  return (
    <main className="min-h-screen bg-black text-white flex flex-col font-sans selection:bg-purple-500 selection:text-white overflow-clip">

      <AnimatePresence>
        {currentStep === 'upload' && (
          <motion.header
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed top-0 left-0 w-full p-6 z-50 flex justify-between items-center mix-blend-difference pointer-events-none"
          >
            <div className="text-xl font-black tracking-tighter">CLINICAL<span className="text-purple-500">SENTINEL</span></div>
          </motion.header>
        )}
      </AnimatePresence>

      {renderNav()}

      <AnimatePresence mode="wait">
        {currentStep === 'upload' ? (
          <motion.div
            key="landing"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.5 } }}
            className="w-full"
          >
            <HeroLanding />

            <div className="relative w-full bg-black text-white py-32 px-6 md:px-12 lg:px-24 max-w-[1400px] mx-auto flex flex-col md:flex-row items-start gap-12 lg:gap-24 border-t border-white/5">
              <NeuralCore />
              <div className="md:w-1/3 sticky top-32 pt-10 relative z-10">
                <h2 className="text-sm font-bold uppercase tracking-[0.2em] text-purple-500 mb-4 flex items-center gap-2">
                  <Brain className="w-4 h-4" /> The Architecture
                </h2>
                <h3 className="text-4xl md:text-5xl lg:text-6xl font-black tracking-tight leading-[1.1] mb-6">
                  Catch Clinical Fraud.<br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-rose-400">
                    Before it Reaches the FDA.
                  </span>
                </h3>
                <p className="text-neutral-400 text-lg md:text-xl font-medium leading-relaxed">
                  The world's first multi-modal clinical trial forensic auditor. Detect data fabrication, temporal drift, and behavioral anomalies using mathematically defensible 7-layer AI.
                </p>
              </div>
              <div className="md:w-2/3 flex flex-col gap-8 md:gap-12 pt-10 md:pt-32 pb-32 relative z-10">
                <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="bg-neutral-900/40 border border-white/5 p-8 md:p-12 rounded-[2rem] hover:bg-neutral-900/60 hover:border-purple-500/30 transition-colors group backdrop-blur-sm">
                  <div className="w-14 h-14 bg-rose-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><Fingerprint className="w-7 h-7 text-rose-500" /></div>
                  <h4 className="text-3xl font-bold mb-4 tracking-tight">6-Layer Forensic Detection</h4>
                  <p className="text-neutral-400 text-lg leading-relaxed">Decomposes anomaly SHAP values into explainable fabrication mechanics, proving biological impossibility across investigative sites.</p>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="bg-neutral-900/40 border border-white/5 p-8 md:p-12 rounded-[2rem] hover:bg-neutral-900/60 hover:border-purple-500/30 transition-colors group backdrop-blur-sm">
                  <div className="w-14 h-14 bg-purple-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><Activity className="w-7 h-7 text-purple-500" /></div>
                  <h4 className="text-3xl font-bold mb-4 tracking-tight">Benford's Law Engine</h4>
                  <p className="text-neutral-400 text-lg leading-relaxed">Mathematically flags subconsciously fabricated numeric distributions, terminal digit entropy, and unnatural round-number clustering.</p>
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="bg-neutral-900/40 border border-white/5 p-8 md:p-12 rounded-[2rem] hover:bg-neutral-900/60 hover:border-purple-500/30 transition-colors group backdrop-blur-sm">
                  <div className="w-14 h-14 bg-emerald-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><Scale className="w-7 h-7 text-emerald-500" /></div>
                  <h4 className="text-3xl font-bold mb-4 tracking-tight">21 CFR Part 11 Reports</h4>
                  <p className="text-neutral-400 text-lg leading-relaxed">Automatically generates digitally-signed, FDA-compliant PDF audit reports grounded in ICH E6(R3) guidelines using RegRAG.</p>
                </motion.div>
              </div>
            </div>

            <div className="relative w-full min-h-screen flex flex-col items-center justify-center py-24 px-4 border-t border-white/5">

              <AmbientAurora />

              <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="w-full max-w-2xl flex flex-col items-center justify-center bg-neutral-900/40 backdrop-blur-3xl p-10 rounded-[2.5rem] border border-white/10 shadow-[0_0_100px_rgba(168,85,247,0.15)] relative z-10">
                <h1 className="text-4xl md:text-5xl font-black tracking-tighter mb-8 text-center">Flawless Data. <br /><span className="text-purple-500">Ready for Production.</span></h1>

                <div className={`w-full border border-dashed ${isUploading ? 'border-transparent bg-transparent' : 'border-white/20 bg-white/[0.02] hover:bg-white/[0.05] cursor-pointer hover:border-purple-500/50'} rounded-[2rem] p-8 min-h-[280px] transition-all duration-500 flex flex-col items-center justify-center group relative overflow-hidden`}
                  onClick={() => !isUploading && fileInputRef.current?.click()}
                >
                  <input type="file" className="hidden" accept=".csv,.xlsx,.xls,.json" ref={fileInputRef} onChange={handleFileChange} disabled={isUploading} />

                  {isUploading ? (
                    <div className="flex flex-col items-center justify-center w-full h-full z-10">
                      <AnimatePresence mode="wait">
                        {uploadProgress < 100 ? (
                          <motion.div
                            key="uploading-ring"
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9, filter: "blur(10px)" }}
                            className="flex flex-col items-center"
                          >
                            <div className="relative w-32 h-32 mb-6 flex items-center justify-center">
                              <svg className="absolute inset-0 w-full h-full transform -rotate-90">
                                <circle cx="64" cy="64" r={radius} className="stroke-neutral-800" strokeWidth="8" fill="transparent" />
                              </svg>
                              <svg className="absolute inset-0 w-full h-full transform -rotate-90 drop-shadow-[0_0_12px_rgba(34,211,238,0.4)]">
                                <motion.circle
                                  cx="64" cy="64" r={radius}
                                  className="stroke-cyan-400"
                                  strokeWidth="8" fill="transparent"
                                  strokeDasharray={circumference}
                                  initial={{ strokeDashoffset: circumference }}
                                  animate={{ strokeDashoffset }}
                                  transition={{ ease: "linear", duration: 0.2 }}
                                  strokeLinecap="round"
                                />
                              </svg>
                              <span className="text-3xl font-black text-cyan-400 font-mono tracking-tighter">{uploadProgress}%</span>
                            </div>
                            <p className="font-mono text-sm tracking-wide text-cyan-500">
                              {uploadedBytes ? `${formatMB(uploadedBytes.loaded)}MB / ${formatMB(uploadedBytes.total)}MB Transferred` : "Establishing Secure Uplink..."}
                            </p>
                          </motion.div>
                        ) : (
                          <motion.div
                            key="processing-terminal"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="w-full bg-black/80 border border-cyan-900/50 rounded-xl p-6 shadow-[inset_0_0_30px_rgba(6,182,212,0.05)]"
                          >
                            <div className="flex items-center gap-3 mb-4 border-b border-cyan-900/30 pb-3">
                              <QuantumLoader />
                              <span className="text-sm font-bold uppercase tracking-widest text-cyan-400">Engine Telemetry</span>
                            </div>

                            <div className="space-y-2 mb-3 h-[70px] overflow-hidden flex flex-col justify-end relative">
                              {/* BUG FIX: Boot Sequence Shimmer logic updated to show while waiting for server or history */}
                              {(statusHistory.length === 0 || processingStatus === "File transferred. Server digesting dataset payload...") && (
                                <motion.div
                                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                                  className="absolute inset-0 flex flex-col justify-end pb-2 space-y-2 pointer-events-none"
                                >
                                  <div className="h-1.5 w-3/4 bg-cyan-900/40 rounded animate-pulse" />
                                  <div className="h-1.5 w-1/2 bg-cyan-900/40 rounded animate-pulse" style={{ animationDelay: '150ms' }} />
                                  <div className="h-1.5 w-5/6 bg-cyan-900/40 rounded animate-pulse" style={{ animationDelay: '300ms' }} />
                                </motion.div>
                              )}

                              <AnimatePresence initial={false}>
                                {statusHistory.map((status, i) => (
                                  <motion.p
                                    key={`${status}-${i}`}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 0.5, x: 0 }}
                                    className="font-mono text-xs text-cyan-600 flex items-center relative z-10"
                                  >
                                    <CheckCircle className="w-3.5 h-3.5 mr-2 shrink-0" /> <span className="truncate">{status}</span>
                                  </motion.p>
                                ))}
                              </AnimatePresence>
                            </div>

                            <motion.p
                              key={processingStatus}
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              className="font-mono text-sm text-cyan-300 flex items-center"
                            >
                              <span className="mr-2 text-cyan-500 animate-pulse">❯</span> <span className="truncate">{processingStatus}</span>
                            </motion.p>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                      <div className="p-4 bg-white/5 rounded-full mb-4 group-hover:bg-purple-500/20 transition-colors">
                        <UploadCloud className="w-8 h-8 text-neutral-300 group-hover:text-purple-400 transition-colors" />
                      </div>
                      <p className="text-xl font-medium mb-2 tracking-tight">Secure Upload</p>
                      <p className="text-sm text-neutral-500">Drop your CSV, JSON, or Excel file here.</p>
                    </div>
                  )}

                  {isUploading && uploadProgress < 100 && (
                    <motion.div
                      className="absolute inset-0 bg-cyan-500/5 pointer-events-none rounded-[2rem]"
                      animate={{ opacity: [0, 0.5, 0] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                  )}
                </div>

                {!isUploading && samples.length > 0 && (
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
                  <div className="mt-8 flex justify-end"><button onClick={() => setCurrentStep('forensic')} className="px-6 py-3 bg-white text-black font-medium rounded-xl shadow-lg hover:bg-neutral-200 transition-colors">Forensic Audit &rarr;</button></div>
                </motion.div>
              )}
              {/* NEW TAB RENDERED HERE */}
              {currentStep === 'forensic' && (
                <motion.div key="forensic" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
                  {sessionId && <FRIDashboard key={sessionId} sessionId={sessionId} columns={columns} />}
                  <div className="mt-8 flex justify-end"><button onClick={() => setCurrentStep('insights')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors">Regulatory Report &rarr;</button></div>
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