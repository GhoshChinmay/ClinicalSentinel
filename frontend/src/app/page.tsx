"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, Loader2, ShieldCheck, Trash2, Edit, BarChart, Brain, Terminal, AlertOctagon, XCircle, X, ArrowRight, FileCheck } from "lucide-react";
import api from "@/lib/api";
import type { UploadResponse } from "@/types/api";

// Component Imports
import Detection from "../components/Detection";
import Clean from "../components/Clean";
import ReviewEdit from "../components/ReviewEdit";
import Visualizer from "../components/Visualizer";
import Insights from "../components/Insights";
import Query from "../components/Query";
import Compare from "../components/Compare";
import ExportReport from "../components/ExportReport";

// Define the stages of our pipeline
type PipelineStep = 'upload' | 'detect' | 'insights' | 'clean' | 'compare' | 'edit' | 'visualize' | 'query' | 'report';

export default function Home() {
  const [currentStep, setCurrentStep] = useState<PipelineStep>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // --- Cached Insights (survives tab switches) ---
  const [cachedInsights, setCachedInsights] = useState<Array<{observation: string; insight: string; action: string}> | null>(null);

  // --- NEW: State for AI Recommended Cleaning ---
  const [recommendedMethod, setRecommendedMethod] = useState<string>('quarantine');
  const [cleaningRationale, setCleaningRationale] = useState<string>('');

  // State to hold the Gatekeeper contract errors
  const [contractErrors, setContractErrors] = useState<string[] | null>(null);
  // State for general upload errors
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- NEW: Sample Library ---
  const [samples, setSamples] = useState<Array<{filename: string, name: string, rows: number, anomalies: number, description: string, icon: string}>>([]);

  useEffect(() => {
    api.get('/api/samples').then(res => setSamples(res.data.samples)).catch(console.error);
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      await processUpload(selectedFile);
    }
  };

  const processUpload = async (uploadFile: File) => {
    setIsUploading(true);
    setUploadError(null);
    setContractErrors(null);
    const formData = new FormData();
    formData.append("file", uploadFile);

    try {
      const response = await api.post<UploadResponse>("/api/upload/", formData);
      setSessionId(response.data.session_id);
      setCachedInsights(null); // Clear stale insights from prior session

      // --- Capture the AI recommendations from the backend ---
      setRecommendedMethod(response.data.recommended_cleaning || 'quarantine');
      setCleaningRationale(response.data.cleaning_rationale || '');

      // Automatically move to the detection phase once uploaded
      setCurrentStep('detect');
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: {
          status?: number;
          data?: {
            status?: string;
            errors?: string[];
            error?: string;
          };
        };
        message?: string;
      };

      const respData = axiosErr.response?.data;

      if (axiosErr.response?.status === 400 && respData?.errors?.length) {
        // Schema validation errors from SchemaEnforcer
        setContractErrors(respData.errors);
      } else {
        const errorMessage = respData?.error || axiosErr.message || "Unknown error occurred";
        console.error("Upload Error Details:", errorMessage);
        setUploadError(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
      }
    } finally {
      setIsUploading(false);
    }
  };

  const loadSample = async (filename: string) => {
    setIsUploading(true);
    setUploadError(null);
    setContractErrors(null);
    try {
      const response = await api.post<UploadResponse>(`/api/load-sample/${filename}`);
      setSessionId(response.data.session_id);
      setCachedInsights(null);
      setRecommendedMethod(response.data.recommended_cleaning || 'quarantine');
      setCleaningRationale(response.data.cleaning_rationale || '');
      setCurrentStep('detect');
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: {
          status?: number;
          data?: { status?: string; errors?: string[]; error?: string; };
        };
        message?: string;
      };

      const respData = axiosErr.response?.data;

      if (axiosErr.response?.status === 400 && respData?.errors?.length) {
        setContractErrors(respData.errors);
      } else {
        const errorMessage = respData?.error || axiosErr.message || "Unknown error occurred";
        console.error("Upload Error Details:", errorMessage);
        setUploadError(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
      }
    } finally {
      setIsUploading(false);
    }
  };

  // The Sleek Top Navigation Bar (REORDERED)
  const renderNav = () => {
    if (currentStep === 'upload') return null;

    const steps = [
      { id: 'detect', icon: <ShieldCheck size={16} />, label: 'Detection' },
      { id: 'insights', icon: <Brain size={16} />, label: 'Insights' }, // Moved before Cleaning
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
          <button
            key={step.id}
            onClick={() => setCurrentStep(step.id as PipelineStep)}
            disabled={!sessionId}
            className={`flex items-center px-4 py-2 rounded-xl text-xs md:text-sm font-bold transition-all whitespace-nowrap
              ${currentStep === step.id ? 'bg-white text-black shadow-lg' : 'text-neutral-500 hover:text-white hover:bg-neutral-900'}
            `}
          >
            <span className="mr-2">{step.icon}</span>
            {step.label}
          </button>
        ))}
      </nav>
    );
  };

  return (
    <main className="min-h-screen bg-[#050505] text-white flex flex-col font-sans">
      {renderNav()}

      <div className="flex-1 flex flex-col items-center p-6 w-full max-w-6xl mx-auto">
        <AnimatePresence mode="wait">

          {/* STEP 1: LANDING PAGE */}
          {currentStep === 'upload' && (
            <motion.div key="upload" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="w-full max-w-2xl mt-20 flex flex-col items-center justify-center min-h-[70vh]">
              <div className="text-center mb-12">
                <h1 className="text-6xl font-black mb-4 tracking-tighter text-center">
                  Data<span className="text-neutral-600">Sentinel</span>
                </h1>
                <p className="text-neutral-500 text-lg max-w-md mx-auto">Secure, local-first data observability and cleaning for the modern enterprise.</p>
              </div>

              <div
                className="w-full border-2 border-dashed border-neutral-800 bg-neutral-900/40 hover:bg-neutral-900/80 rounded-3xl p-16 transition-all duration-300 flex flex-col items-center justify-center cursor-pointer group"
                onClick={() => fileInputRef.current?.click()}
              >
                <input type="file" className="hidden" accept=".csv,.xlsx,.xls,.json" ref={fileInputRef} onChange={handleFileChange} />

                {isUploading ? (
                  <div className="flex flex-col items-center text-blue-400">
                    <Loader2 className="w-10 h-10 animate-spin mb-4" />
                    <p className="font-medium tracking-wide">Initializing Pipeline...</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center group-hover:scale-105 transition-transform duration-300">
                    <div className="p-5 bg-white text-black rounded-full mb-6 shadow-xl">
                      <UploadCloud className="w-8 h-8" />
                    </div>
                    <p className="text-xl font-bold mb-2">Upload Dataset</p>
                    <div className="flex gap-2 justify-center mb-2">
                      <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs font-bold font-mono">.CSV</span>
                      <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs font-bold font-mono">.XLSX</span>
                      <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs font-bold font-mono">.JSON</span>
                    </div>
                    <p className="text-sm text-neutral-500">Max size: 100MB</p>
                  </div>
                )}
              </div>

              {/* Upload Error Banner */}
              {uploadError && (
                <div className="mt-4 w-full p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start text-red-400">
                  <XCircle className="w-5 h-5 mr-3 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-bold text-sm mb-1">Upload Failed</p>
                    <p className="text-sm text-red-300/80">{uploadError}</p>
                  </div>
                  <button onClick={() => setUploadError(null)} className="ml-4 text-red-400 hover:text-white"><X className="w-4 h-4" /></button>
                </div>
              )}

              {/* NEW: Sample Datasets */}
              {samples.length > 0 && (
                <div className="w-full mt-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
                  <div className="flex justify-between items-end mb-4">
                    <div>
                      <h3 className="text-lg font-bold">Sample Library</h3>
                      <p className="text-sm text-neutral-500">Try DataSentinel with pre-engineered test cases.</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {samples.map((sample) => (
                      <div
                        key={sample.filename}
                        className="bg-neutral-900/40 hover:bg-neutral-800/80 border border-neutral-800 p-4 rounded-2xl cursor-pointer transition-all hover:scale-[1.02] active:scale-95 group relative overflow-hidden"
                        onClick={() => loadSample(sample.filename)}
                      >
                        {/* Highlight effect */}
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                        
                        <div className="flex justify-between items-start mb-3 relative z-10">
                          <span className="text-2xl">{sample.icon}</span>
                          <div className="flex flex-col items-end">
                            <span className="text-xs font-mono text-neutral-500">{sample.rows.toLocaleString()} rows</span>
                            <span className="text-xs font-mono text-red-500">{sample.anomalies.toLocaleString()} anomalies</span>
                          </div>
                        </div>
                        <h4 className="font-bold text-sm mb-1 relative z-10">{sample.name}</h4>
                        <p className="text-xs text-neutral-400 line-clamp-2 relative z-10">{sample.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* STEP 2: DETECTION */}
          {currentStep === 'detect' && (
            <motion.div key="detect" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Anomaly Detection Engine</h2>
                <p className="text-neutral-400">Review the corrupted rows and understand exactly why the AI flagged them.</p>
              </div>
              {sessionId && <Detection key={sessionId} sessionId={sessionId} />}

              <div className="mt-8 flex justify-end">
                {/* Updated flow: Detection -> Insights */}
                <button onClick={() => setCurrentStep('insights')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors shadow-lg">
                  Proceed to AI Insights &rarr;
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 3: INSIGHTS (MOVED HERE) */}
          {currentStep === 'insights' && (
            <motion.div key="insights" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">AI Contextual Insights</h2>
                <p className="text-neutral-400">A structured OIA (Observation, Insight, Action) analysis of your data.</p>
              </div>
              {sessionId && <Insights sessionId={sessionId} cachedInsights={cachedInsights} onInsightsLoaded={setCachedInsights} />}

              <div className="mt-8 flex justify-end">
                {/* Added flow: Insights -> Cleaning */}
                <button onClick={() => setCurrentStep('clean')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors shadow-lg">
                  Proceed to Smart Cleaning &rarr;
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 4: CLEANING */}
          {currentStep === 'clean' && (
            <motion.div key="clean" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-5xl mt-10">
              <div className="mb-6 text-center">
                <h2 className="text-2xl font-semibold mb-1">Smart Cleaning Strategy</h2>
                <p className="text-neutral-400">Choose how the AI should handle the anomalies detected in your dataset.</p>
              </div>
              {sessionId && (
                <Clean
                  key={sessionId}
                  sessionId={sessionId}
                  onComplete={() => setCurrentStep('compare')}
                  recommendedMethod={recommendedMethod}
                  cleaningRationale={cleaningRationale}
                />
              )}
            </motion.div>
          )}

          {/* STEP 5: A/B COMPARISON */}
          {currentStep === 'compare' && (
            <motion.div key="compare" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">A/B Repair Comparison</h2>
                <p className="text-neutral-400">Review the high-fidelity modifications made by the predictive AI imputer.</p>
              </div>
              {sessionId && <Compare key={sessionId} sessionId={sessionId} />}

              <div className="mt-8 flex justify-end">
                <button onClick={() => setCurrentStep('edit')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors shadow-lg">
                  Proceed to Review & Edit &rarr;
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 6: REVIEW & EDIT */}
          {currentStep === 'edit' && (
            <motion.div key="edit" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Review & Edit</h2>
                <p className="text-neutral-400">Your data has been sanitized. You can now make manual overrides before exporting.</p>
              </div>
              {sessionId && <ReviewEdit key={sessionId} sessionId={sessionId} />}
            </motion.div>
          )}

          {/* STEP 7: VISUALIZER */}
          {currentStep === 'visualize' && (
            <motion.div key="viz" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Dataset Visualizer</h2>
                <p className="text-neutral-400">Explore the macro-level impact of sanitization and discover variable correlations.</p>
              </div>
              {sessionId && <Visualizer key={sessionId} sessionId={sessionId} />}
            </motion.div>
          )}

          {/* STEP 8: QUERY */}
          {currentStep === 'query' && (
            <motion.div key="query" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Text-to-Query Engine</h2>
                <p className="text-neutral-400">Ask complex questions in English and watch the AI execute them instantly.</p>
              </div>
              {sessionId && <Query key={sessionId} sessionId={sessionId} />}

              <div className="mt-8 flex justify-end">
                <button onClick={() => setCurrentStep('report')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors shadow-lg">
                  Final Quality Report &rarr;
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 9: REPORT & EXPORT */}
          {currentStep === 'report' && (
            <motion.div key="report" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              {sessionId && <ExportReport key={sessionId} sessionId={sessionId} />}
            </motion.div>
          )}

        </AnimatePresence>
      </div>

      {/* --- DATA CONTRACT VIOLATION MODAL --- */}
      <AnimatePresence>
        {contractErrors && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-neutral-900 border border-red-500/30 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"
            >
              <div className="bg-red-500/10 p-6 border-b border-red-500/20 flex items-start justify-between">
                <div className="flex items-center">
                  <div className="bg-red-500/20 p-3 rounded-xl mr-4">
                    <AlertOctagon className="w-8 h-8 text-red-500" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">Data Contract Violation</h2>
                    <p className="text-red-400 text-sm mt-1">Upload rejected by the Gatekeeper.</p>
                  </div>
                </div>
                <button onClick={() => setContractErrors(null)} className="text-neutral-500 hover:text-white transition-colors">
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="p-6">
                <p className="text-neutral-300 text-sm mb-4">
                  The dataset you attempted to upload does not meet the minimum requirements for machine learning processing. Please resolve the following issues:
                </p>

                <ul className="space-y-3 mb-6">
                  {contractErrors.map((error, idx) => (
                    <li key={idx} className="flex items-start bg-black/40 p-3 rounded-lg border border-neutral-800">
                      <XCircle className="w-5 h-5 text-red-500 mr-3 shrink-0 mt-0.5" />
                      <span className="text-neutral-300 text-sm leading-relaxed">{error}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => setContractErrors(null)}
                  className="w-full py-3 bg-neutral-800 hover:bg-neutral-700 text-white font-bold rounded-xl transition-colors border border-neutral-700"
                >
                  Acknowledge & Try Again
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </main>
  );
}