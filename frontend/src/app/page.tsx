"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, Database, Loader2, ShieldCheck, Trash2, Edit, BarChart, Brain, Terminal } from "lucide-react";
import axios from "axios";

// Component Imports
import Detection from "../components/Detection";
import Clean from "../components/Clean";
import ReviewEdit from "../components/ReviewEdit";
import Visualizer from "../components/Visualizer";
import Insights from "../components/Insights";
import Query from "../components/Query";

// Define the stages of our pipeline
type PipelineStep = 'upload' | 'detect' | 'clean' | 'edit' | 'visualize' | 'insights' | 'query';

export default function Home() {
  const [currentStep, setCurrentStep] = useState<PipelineStep>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      await processUpload(selectedFile);
    }
  };

  const processUpload = async (uploadFile: File) => {
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", uploadFile);

    try {
      const response = await axios.post("http://127.0.0.1:8000/api/upload", formData);
      setSessionId(response.data.session_id);
      // Automatically move to the detection phase once uploaded
      setCurrentStep('detect');
    } catch (err: any) {
      // Unmask the exact error from the Python backend!
      const errorMessage = err.response?.data?.detail || err.message || "Unknown error occurred";
      console.error("Upload Error Details:", errorMessage);

      // Pop up an alert so you can see it right on the screen
      alert(`Upload Failed: ${errorMessage}`);
    } finally {
      setIsUploading(false);
    }
  };

  // The Sleek Top Navigation Bar
  const renderNav = () => {
    if (currentStep === 'upload') return null;

    const steps = [
      { id: 'detect', icon: <ShieldCheck size={16} />, label: 'Detection' },
      { id: 'clean', icon: <Trash2 size={16} />, label: 'Cleaning' },
      { id: 'edit', icon: <Edit size={16} />, label: 'Edit' },
      { id: 'visualize', icon: <BarChart size={16} />, label: 'Visualizer' },
      { id: 'insights', icon: <Brain size={16} />, label: 'Insights' },
      { id: 'query', icon: <Terminal size={16} />, label: 'Query' }
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
                <input type="file" className="hidden" accept=".csv" ref={fileInputRef} onChange={handleFileChange} />

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
                    <p className="text-xl font-bold mb-2">Select Dataset</p>
                    <p className="text-sm text-neutral-500">Supports CSV files up to 100MB</p>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* STEP 2: DETECTION */}
          {currentStep === 'detect' && (
            <motion.div key="detect" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Anomaly Detection Engine</h2>
                <p className="text-neutral-400">Review the corrupted rows and understand exactly why the AI flagged them.</p>
              </div>
              {/* Added key={sessionId} to force React to unmount/remount on new sessions */}
              {sessionId && <Detection key={sessionId} sessionId={sessionId} />}

              {/* Navigation Button to next step */}
              <div className="mt-8 flex justify-end">
                <button onClick={() => setCurrentStep('clean')} className="px-6 py-3 bg-white text-black font-medium rounded-xl hover:bg-neutral-200 transition-colors shadow-lg">
                  Proceed to Smart Cleaning &rarr;
                </button>
              </div>
            </motion.div>
          )}

          {/* STEP 3: CLEANING */}
          {currentStep === 'clean' && (
            <motion.div key="clean" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-5xl mt-10">
              <div className="mb-6 text-center">
                <h2 className="text-2xl font-semibold mb-1">Smart Cleaning Strategy</h2>
                <p className="text-neutral-400">Choose how the AI should handle the anomalies detected in your dataset.</p>
              </div>
              {/* Added key={sessionId} */}
              {sessionId && <Clean key={sessionId} sessionId={sessionId} onComplete={() => setCurrentStep('edit')} />}
            </motion.div>
          )}

          {/* STEP 4: REVIEW & EDIT */}
          {currentStep === 'edit' && (
            <motion.div key="edit" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Review & Edit</h2>
                <p className="text-neutral-400">Your data has been sanitized. You can now make manual overrides before exporting.</p>
              </div>
              {/* Added key={sessionId} */}
              {sessionId && <ReviewEdit key={sessionId} sessionId={sessionId} />}
            </motion.div>
          )}

          {/* STEP 5: VISUALIZER */}
          {currentStep === 'visualize' && (
            <motion.div key="viz" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Dataset Visualizer</h2>
                <p className="text-neutral-400">Explore the macro-level impact of sanitization and discover variable correlations.</p>
              </div>
              {/* Added key={sessionId} */}
              {sessionId && <Visualizer key={sessionId} sessionId={sessionId} />}
            </motion.div>
          )}

          {/* STEP 6: INSIGHTS */}
          {currentStep === 'insights' && (
            <motion.div key="insights" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">AI Contextual Insights</h2>
                <p className="text-neutral-400">A plain-English summary of your data, generated securely on your local machine.</p>
              </div>
              {/* Added key={sessionId} */}
              {sessionId && <Insights key={sessionId} sessionId={sessionId} />}
            </motion.div>
          )}

          {/* STEP 7: QUERY */}
          {currentStep === 'query' && (
            <motion.div key="query" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full mt-10">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-1">Text-to-Query Engine</h2>
                <p className="text-neutral-400">Ask complex questions in English and watch the AI execute them instantly.</p>
              </div>
              {/* Added key={sessionId} */}
              {sessionId && <Query key={sessionId} sessionId={sessionId} />}
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </main>
  );
}