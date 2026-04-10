"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { 
  Play, 
  Sparkles, 
  BarChart3, 
  Video, 
  Camera,
  Cpu
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";
import { BentoGrid, BentoCard } from "@/components/BentoGrid";
import { StatusConsole } from "@/components/StatusConsole";
import { VisualCache } from "@/components/VisualCache";
import { cn } from "@/lib/utils";
import { useAnalytics } from "@/lib/useAnalytics";
import { useToast } from "@/components/ToastProvider";
import { logoutAction } from "@/app/login/actions";
const HeroGlobe = dynamic(() => import("@/components/HeroGlobe").then(mod => mod.HeroGlobe), { 
  ssr: false,
  loading: () => (
    <div className="fixed top-0 left-0 w-full h-full pointer-events-none -z-20 opacity-30">
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-200 rounded-full blur-[120px]" />
    </div>
  )
});

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-secret-key-123";

/** Shape of GET /jobs/{id} used by the dashboard */
export interface JobSceneRow {
  scene_number: number;
  keyframe_url?: string;
  motion_url?: string;
  status?: string;
  lighting_prompt?: string;
  light_source_origin?: string;
  spatial_layout?: string;
  motion_intensity?: string;
}

interface JobLogEntry {
  id: string;
  agent: string;
  message: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

interface JobStatusPayload {
  status?: string;
  pipeline_stage?: string;
  video_url?: string;
  scenes?: JobSceneRow[];
  logs?: JobLogEntry[];
}

const fetchJobStatus = async (jobId: string): Promise<JobStatusPayload | null> => {
  if (!jobId) return null;
  
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    headers: {
      "X-API-Key": API_KEY,
    },
  });
  
  if (!response.ok) {
    throw new Error("Failed to fetch job status");
  }
  
  const row = (await response.json()) as Record<string, unknown>;
  
  const incomingLogs = (row.logs as JobLogEntry[]) || [];
  const stageLog: JobLogEntry = { 
    id: `stage-${String(row.pipeline_stage || "init")}`, 
    agent: "Pipeline", 
    message: `Current Stage: ${String(row.pipeline_stage ?? "Orchestrating")}`, 
    timestamp: new Date().toLocaleTimeString() 
  };

  return {
    ...row,
    logs: [stageLog, ...incomingLogs],
  } as JobStatusPayload;
};

export default function Home() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [logs, setLogs] = useState<JobLogEntry[]>([]);
  const [lastStage, setLastStage] = useState<string>("");
  const [prompt, setPrompt] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [activeView, setActiveView] = useState<"keyframes" | "motion">("keyframes");
  const [selectedStyle, setSelectedStyle] = useState<string | null>(null);
  const [charDesign, setCharDesign] = useState<string>("");
  const [isCharLocked, setIsCharLocked] = useState(false);

  const stylePresets = [
    { id: "cinema", name: "IMAX 70mm", icon: "🎥", suffix: "shot on 70mm film, imax cinematic lighting, hyper-realistic, high fidelity" },
    { id: "noir", name: "Noir Mystery", icon: "🌫️", suffix: "low-key lighting, moody atmospheric shadows, noir aesthetic, grainy 35mm film" },
    { id: "cyber", name: "Cyberpunk", icon: "🏮", suffix: "neon saturated colors, blade runner aesthetic, futuristic bokeh, sharp reflections" },
    { id: "anime", name: "Studio Ghibli", icon: "✨", suffix: "hand-painted ghibli style, vibrant watercolor, whimsical atmosphere, soft lighting" },
    { id: "retro", name: "VHS 90s", icon: "📼", suffix: "vintage vhs aesthetic, tracking artifacts, 90s low-fi home video style" },
  ];

  const { trackEvent } = useAnalytics();
  const { toast } = useToast();

  const { data: job } = useQuery({
    queryKey: ["job", activeJobId],
    queryFn: (): Promise<JobStatusPayload | null> => fetchJobStatus(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === "COMPLETED" || data?.status === "FAILED" || data?.status === "HITL_PAUSE") {
        return false;
      }
      return 3000; // Increased frequency for precision
    },
  });

  const handleJobUpdates = useCallback((currentJob: JobStatusPayload | null | undefined, currentLastStage: string) => {
    if (!currentJob) return;
    if (currentJob.logs && currentJob.logs.length > 0) {
      setLogs((prev) => {
        const existingIds = new Set(prev.map(l => l.id));
        const newLogs = currentJob.logs!.filter(l => !existingIds.has(l.id));
        if (newLogs.length === 0) return prev;
        return [...prev, ...newLogs];
      });
    }
    const stage = currentJob.pipeline_stage;
    if (stage && stage !== currentLastStage) {
      setLastStage(stage);
      if (currentJob.status === "HITL_PAUSE") {
        toast({ title: "Human-In-The-Loop Required", description: "The agent pipeline has paused for your approval.", type: "agent" });
      } else if (currentJob.status === "COMPLETED") {
        setShowSuccess(true);
        trackEvent("job_completed", { jobId: activeJobId });
        toast({ title: "Production Completed", description: "Your 11-agent episode is rendered.", type: "success" });
      }
    }
  }, [activeJobId, toast, trackEvent]);

  useEffect(() => {
    handleJobUpdates(job, lastStage);
  }, [job, lastStage, handleJobUpdates]);

  const handleSubmitBlueprint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt) return;
    
    setIsStarting(true);
    try {
      const styleSuffix = selectedStyle ? stylePresets.find(s => s.id === selectedStyle)?.suffix : "";
      const finalPrompt = `${prompt} ${styleSuffix}`.trim();

      const response = await fetch(`${API_BASE_URL}/jobs/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({
          raw_prompt: finalPrompt,
          chat_id: "web-client-user",
          character_design: isCharLocked ? charDesign : undefined
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to start job");
      }
      
      const data = await response.json();
      setActiveJobId(data.job_id);
    } catch (err: unknown) {
      console.error("Error starting job:", err);
      const msg = err instanceof Error ? err.message : String(err);
      toast({ title: "Blueprint Configuration Error", description: msg, type: "error" });
    } finally {
      setIsStarting(false);
      trackEvent("job_started", { promptLength: prompt.length });
      toast({ title: "Pipeline Swarm Activated", description: "11 agents are now parsing your blueprint.", type: "info" });
    }
  };

  const handleResumeJob = async () => {
    if (!activeJobId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/jobs/${activeJobId}/resume`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({ action: "APPROVE" })
      });
      if (!response.ok) throw new Error("Failed to resume job");
      toast({ title: "Production Resumed", description: "Keyframes approved. Sending to video agents.", type: "success" });
      trackEvent("scene_approved", { jobId: activeJobId });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast({ title: "Agent Sync Failed", description: msg, type: "error" });
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden">
      <HeroGlobe />
      
      <nav className="relative z-50 flex justify-between items-center p-4 mt-8 max-w-7xl mx-auto glass-card rounded-[2rem] shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)] ring-1 ring-slate-900/5 backdrop-blur-3xl">
        <div className="flex items-center gap-3 px-2">
          <div className="bg-gradient-to-tr from-indigo-600 to-violet-600 p-2.5 rounded-2xl text-white shadow-lg shadow-indigo-200/50">
            <Sparkles size={20} />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            ZeroGPU <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">Studio</span>
          </h1>
        </div>
        <div className="hidden md:flex gap-8 text-sm font-bold text-slate-400 px-4">
          <a href="#" className="hover:text-slate-900 transition-colors">Documentation</a>
          <a href="#" className="hover:text-slate-900 transition-colors">API Keys</a>
          <a href="#" className="hover:text-slate-900 transition-colors">Archive</a>
        </div>
        <div className="flex items-center gap-4 px-2">
          <button
            type="button"
            onClick={() => logoutAction()}
            className="text-slate-500 hover:text-slate-900 text-sm font-bold transition-all px-4"
          >
            Logout
          </button>
          <button className="bg-slate-900 text-white text-sm font-bold px-6 py-2.5 rounded-full hover:bg-slate-800 transition-all shadow-xl active:scale-95 border border-white/10 hover:border-white/20">
            Connect n8n
          </button>
        </div>
      </nav>

      {/* --- CELEBRATORY SUCCESS MODAL --- */}
      <AnimatePresence>
        {showSuccess && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-white/40 backdrop-blur-2xl"
          >
            <motion.div 
              initial={{ scale: 0.9, y: 20, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              transition={{ type: "spring", damping: 20, stiffness: 300 }}
              className="bg-white border border-indigo-100 rounded-[32px] p-12 shadow-[0_32px_128px_-16px_rgba(99,102,241,0.2)] max-w-lg w-full text-center relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-indigo-500 via-sky-400 to-indigo-500 animate-gradient-x" />
              
              <div className="bg-indigo-600 w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-8 shadow-2xl shadow-indigo-200">
                <Sparkles className="text-white" size={48} />
              </div>

              <h2 className="text-4xl font-black text-slate-900 tracking-tight mb-4">
                PRODUCTION <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">DELIVERED</span>
              </h2>
              
              <p className="text-slate-500 font-medium mb-10 leading-relaxed">
                Your 11-agent cinematic episode has been fully rendered and graduated to production. Every keyframe, voiceover, and motion clip is now ready.
              </p>

              <div className="grid grid-cols-2 gap-4 mb-10">
                <div className="bg-slate-50 rounded-2xl p-4 border border-slate-100">
                  <p className="text-[10px] font-black uppercase text-slate-400 mb-1 tracking-widest">Quality</p>
                  <p className="text-xl font-bold text-slate-900">4K ULTRA</p>
                </div>
                <div className="bg-indigo-50/50 rounded-2xl p-4 border border-indigo-100">
                  <p className="text-[10px] font-black uppercase text-indigo-400 mb-1 tracking-widest">Status</p>
                  <p className="text-xl font-bold text-indigo-600">GRADUATED</p>
                </div>
              </div>

              <button 
                onClick={() => setShowSuccess(false)}
                className="w-full bg-slate-900 text-white py-5 rounded-2xl text-lg font-bold shadow-xl hover:bg-slate-800 transition-all active:scale-95"
              >
                ACCESS FINAL MASTER
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>



      <BentoGrid className="relative z-10 pt-12 pb-24 max-w-[90rem] mx-auto">
        {/* HERO ROW: MASSIVE PRODUCTION MONITOR */}
        <BentoCard 
          className="lg:col-span-6 overflow-visible shadow-[0_40px_100px_-20px_rgba(99,102,241,0.1)] min-h-[500px]"
          title="Production Monitor"
          description="High-Fidelity Visual Sequence Control."
          icon={<Video size={18} />}
        >
          <div className="h-full flex flex-col pt-6">
            {!activeJobId ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-12 rounded-[2.5rem] bg-indigo-50/20 border border-indigo-100/30 relative overflow-hidden group">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[150%] h-[150%] bg-indigo-100/30 rounded-full blur-[160px] -z-10 pointer-events-none opacity-40 group-hover:opacity-60 transition-opacity duration-1000" />
                
                <div className="bg-white p-6 rounded-[2rem] shadow-[0_20px_40px_-10px_rgba(0,0,0,0.08)] border border-slate-100 mb-8 transform group-hover:scale-110 transition-transform duration-700">
                  <Sparkles className="text-indigo-600" size={48} />
                </div>
                
                <h2 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tighter mb-4 flex items-center gap-4">
                  <Camera size={32} className="text-indigo-600" />
                  Orchestrate Sequence
                </h2>
                
                {/* --- 🎭 STYLE PRESETS GALLERY --- */}
                <div className="w-full max-w-3xl mb-8">
                   <div className="flex items-center gap-2 mb-3 text-[10px] font-black uppercase text-indigo-400 tracking-[0.2em]">
                     <Sparkles size={12} />
                     PRODUCTION STYLE LIBRARY
                   </div>
                   <div className="flex gap-4 overflow-x-auto pb-4 custom-scrollbar pr-2">
                     {stylePresets.map(style => (
                       <button
                         key={style.id}
                         onClick={() => setSelectedStyle(selectedStyle === style.id ? null : style.id)}
                         className={cn(
                           "flex-none flex items-center gap-3 px-6 py-4 rounded-[1.5rem] border-2 transition-all active:scale-95",
                           selectedStyle === style.id 
                             ? "bg-slate-900 border-slate-900 text-white shadow-xl scale-105" 
                             : "bg-white border-slate-100 text-slate-500 hover:border-indigo-200"
                         )}
                       >
                         <span className="text-xl">{style.icon}</span>
                         <span className="text-sm font-black whitespace-nowrap">{style.name}</span>
                       </button>
                     ))}
                   </div>
                </div>

                {/* --- 🧬 CHARACTER CONTINUITY STUDIO --- */}
                <div className="w-full max-w-3xl mb-10 p-6 bg-white rounded-[2rem] border border-slate-100 shadow-[0_15px_30px_-10px_rgba(0,0,0,0.05)]">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <div className="bg-indigo-600 w-2 h-2 rounded-full animate-pulse" />
                        <span className="text-[10px] font-black uppercase text-slate-900 tracking-[0.2em]">CHARACTER CONTINUITY STUDIO</span>
                      </div>
                      <button 
                        onClick={() => setIsCharLocked(!isCharLocked)}
                        className={cn(
                          "px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all",
                          isCharLocked ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-400 hover:bg-slate-200"
                        )}
                      >
                        {isCharLocked ? "DESIGN LOCKED" : "LOCK APPEARANCE"}
                      </button>
                    </div>
                    <input 
                      type="text"
                      value={charDesign}
                      onChange={(e) => setCharDesign(e.target.value)}
                      placeholder="Describe the main actor (e.g. A tall man with a silver cloak and mechanical arm)..."
                      className="w-full bg-slate-50 border-none px-6 py-4 rounded-xl text-sm font-medium focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-400"
                    />
                </div>

                <p className="text-base text-slate-500 font-medium max-w-[450px] mb-8 leading-relaxed">
                  Enter your narrative sequence logic below. The 11-agent pipeline will render your global masterpiece.
                </p>
                
                <form onSubmit={handleSubmitBlueprint} className="w-full max-w-3xl relative z-10">
                  <div className="relative group/input">
                    <textarea 
                      rows={5}
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="e.g. A noir detective walks through rainy streets while neon lights reflect off a silver pistol..."
                      className="w-full bg-white/70 backdrop-blur-2xl border border-slate-200/80 rounded-[2.5rem] px-8 py-8 pr-32 text-lg font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-300 transition-all shadow-[inset_0_2px_15px_rgba(0,0,0,0.02)] resize-none min-h-[160px]"
                      disabled={isStarting}
                    />
                    
                    <div className="absolute bottom-4 right-4">
                      <button 
                        disabled={isStarting}
                        className="bg-gradient-to-br from-indigo-600 to-violet-700 hover:from-indigo-500 hover:to-violet-600 text-white p-6 rounded-2xl transition-all shadow-[0_20px_40px_-10px_rgba(79,70,229,0.4)] hover:shadow-[0_20px_50px_-10px_rgba(99,102,241,0.6)] active:scale-95 disabled:opacity-50 flex items-center justify-center gap-3 border border-white/20"
                      >
                        {isStarting ? (
                          <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                          <>
                            <Play size={20} fill="currentColor" />
                            <span className="font-black tracking-widest text-[10px] sm:text-xs">COMMENCE</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </form>
              </div>
            ) : (
              <div className="flex-1 bg-slate-900 rounded-[3rem] overflow-hidden relative group shadow-[0_32px_128px_-32px_rgba(0,0,0,0.4)] border border-slate-800">
                {job?.video_url ? (
                  <video src={job.video_url} controls className="w-full h-full object-cover shadow-inner" />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900 text-white p-20 overflow-hidden">
                     <div className="absolute inset-0 opacity-15 pointer-events-none" 
                          style={{ backgroundImage: 'radial-gradient(#6366f1 1.5px, transparent 1.5px)', backgroundSize: '48px 48px' }} />
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-indigo-600/10 rounded-full blur-[200px] pointer-events-none" />
                    
                    <div className="relative z-10 flex flex-col items-center">
                      <div className="w-32 h-32 border-8 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-10 shadow-[0_0_50px_rgba(99,102,241,0.4)]" />
                      
                      <div className="bg-slate-800/80 backdrop-blur-md px-8 py-3 rounded-2xl border border-slate-700/80 mb-6 shadow-2xl">
                        <h3 className="text-sm font-black tracking-[0.3em] uppercase text-indigo-400">
                          {job?.status || "ORCHESTRATING"}
                        </h3>
                      </div>
                      
                      <p className="text-white font-black text-2xl md:text-3xl text-center max-w-xl leading-snug tracking-tight">
                        {job?.pipeline_stage || "Coordinating Multi-Agent Pipeline..."}
                      </p>
                      
                      {job?.status === "HITL_PAUSE" && (
                        <motion.button 
                          initial={{ scale: 0.9, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={async () => {
                            const btn = document.activeElement as HTMLButtonElement;
                            if (btn) btn.disabled = true;
                            await handleResumeJob();
                          }}
                          className="mt-12 bg-white hover:bg-slate-100 text-slate-900 px-12 py-6 rounded-[2rem] text-lg font-black shadow-[0_0_60px_rgba(255,255,255,0.4)] transition-all flex items-center justify-center gap-4 disabled:opacity-50 uppercase tracking-widest"
                        >
                          <Play size={24} fill="currentColor" />
                          APPROVE CINEMATIC RENDER
                        </motion.button>
                      )}

                      <button 
                        onClick={() => { setActiveJobId(null); setLogs([]); setLastStage(""); setShowSuccess(false); }}
                        className="mt-12 text-xs text-slate-500 hover:text-white uppercase tracking-[0.2em] font-black transition-colors bg-white/5 px-6 py-2 rounded-full border border-white/5"
                      >
                        Terminate Pipeline
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </BentoCard>

        {/* SECONDARY ROW: AGENT DATA & METRICS */}
        <BentoCard 
          className="lg:col-span-3 min-h-[480px]"
          title="Agent Telemetry"
          description="Live model-interaction logs."
          icon={<Cpu size={18} />}
        >
          <StatusConsole logs={logs} />
        </BentoCard>

        <BentoCard 
          className="lg:col-span-3 min-h-[480px]"
          title="Resource Metrics"
          description="Efficiency & Pipeline Health."
          icon={<BarChart3 size={18} />}
        >
          <div className="grid grid-cols-2 gap-6 h-full py-4">
            <div className="bg-indigo-50/50 rounded-3xl p-6 flex flex-col justify-center border border-indigo-100/50 hover:bg-indigo-50 transition-colors cursor-default">
              <span className="text-xs uppercase tracking-widest text-indigo-400 font-black mb-2">Compute Cost</span>
              <span className="text-4xl font-black text-indigo-600 tracking-tighter">$0.00</span>
            </div>
            <div className="bg-emerald-50/50 rounded-3xl p-6 flex flex-col justify-center border border-emerald-100/50 hover:bg-emerald-50 transition-colors cursor-default">
              <span className="text-xs uppercase tracking-widest text-emerald-400 font-black mb-2">Agent Health</span>
              <span className="text-lg font-black text-emerald-600 flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]"/> 11 ONLINE
              </span>
            </div>
            <div className="bg-sky-50/50 rounded-3xl p-6 flex flex-col justify-center border border-sky-100/50 hover:bg-sky-50 transition-colors cursor-default">
              <span className="text-xs uppercase tracking-widest text-sky-400 font-black mb-2">Render Optimization</span>
              <span className="text-4xl font-black text-sky-600 tracking-tighter">98%</span>
            </div>
            <div className="bg-slate-50/80 rounded-3xl p-6 flex flex-col justify-center border border-slate-100 hover:bg-slate-100 transition-colors cursor-default">
              <span className="text-xs uppercase tracking-widest text-slate-400 font-black mb-2">Production Time</span>
              <span className="text-4xl font-black text-slate-700 tracking-tighter">1.2m</span>
            </div>
          </div>
        </BentoCard>
      </BentoGrid>

      {/* --- PRODUCTION STORYBOARD SECTION --- */}
      <section className="relative z-10 max-w-[90rem] mx-auto px-6 pb-32 mt-12">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-10 gap-6">
          <div className="max-w-2xl">
             <div className="inline-flex items-center gap-2 mb-4 bg-indigo-50/80 border border-indigo-100/50 px-3 py-1.5 rounded-xl shadow-[0_2px_10px_rgba(99,102,241,0.1)]">
               <div className="bg-indigo-600 w-2 h-2 rounded-full animate-pulse shadow-[0_0_10px_rgba(79,70,229,0.5)]" />
               <span className="text-[10px] font-black uppercase text-indigo-600 tracking-widest leading-none mt-0.5">Live Asset Cache</span>
             </div>
             <h2 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tighter mb-4">Production <span className="text-transparent bg-clip-text bg-gradient-to-br from-indigo-600 to-sky-500">Storyboard</span></h2>
             <p className="text-slate-500 text-sm md:text-base font-medium leading-relaxed">Review, approve, and sequence high-fidelity AI-generated frames curated across the 11-agent cinematic pipeline.</p>
          </div>
          <div className="flex items-center p-1.5 bg-white/70 backdrop-blur-xl border border-slate-200 shadow-xl rounded-2xl relative w-full md:w-auto h-14">
              <div 
                className="absolute inset-y-1.5 w-[calc(50%-6px)] bg-gradient-to-br from-slate-900 to-slate-800 shadow-xl rounded-xl transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] border border-white/10"
                style={{ left: activeView === "keyframes" ? "6px" : "calc(50%)" }}
              />
              <button 
                onClick={() => setActiveView("keyframes")}
                className={cn(
                  "relative z-10 px-6 py-2.5 rounded-xl text-xs font-black transition-colors uppercase tracking-widest w-1/2 md:w-40 flex items-center justify-center gap-2",
                  activeView === "keyframes" ? "text-white" : "text-slate-500 hover:text-slate-700"
                )}
              >
                Keyframes
              </button>
              <button 
                onClick={() => setActiveView("motion")}
                className={cn(
                  "relative z-10 px-6 py-2.5 rounded-xl text-xs font-black transition-colors uppercase tracking-widest w-1/2 md:w-40 flex items-center justify-center gap-2",
                  activeView === "motion" ? "text-white" : "text-slate-500 hover:text-slate-700"
                )}
              >
                Motion
              </button>
          </div>
        </div>

        <div className="relative group">
          <div className="absolute -inset-2 bg-gradient-to-r from-indigo-500/10 via-sky-500/10 to-indigo-500/10 rounded-[3rem] blur-2xl opacity-50 group-hover:opacity-100 transition duration-1000 group-hover:duration-300" />
          <div className="relative bg-white/50 backdrop-blur-2xl border border-white shadow-[0_32px_64px_-16px_rgba(0,0,0,0.05)] rounded-[2.5rem] overflow-hidden">
            <div className="absolute top-0 w-full h-px bg-gradient-to-r from-transparent via-white to-transparent" />
            <div className="absolute top-0 left-0 w-full h-8 bg-gradient-to-b from-white/40 to-transparent pointer-events-none" />
            <div className="p-6 md:p-12">
              <VisualCache 
                scenes={job?.scenes || []} 
                jobId={activeJobId || undefined}
                activeView={activeView} 
                isLoading={isStarting || (!!activeJobId && !job)}
              />
            </div>
          </div>
        </div>
      </section>

      <div className="fixed top-0 left-0 w-full h-full pointer-events-none -z-20 opacity-30">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-200 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-sky-200 rounded-full blur-[120px]" />
      </div>
    </main>
  );
}
