import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Maximize2, X, Download, ExternalLink, CameraOff, Play, Film, Cpu, CheckCircle2, RefreshCw } from "lucide-react";
import { JobSceneRow } from "@/app/page";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ToastProvider";

interface VisualCacheProps {
  scenes: JobSceneRow[];
  jobId?: string;
  isLoading?: boolean;
  activeView?: "keyframes" | "motion";
}

export function VisualCache({ scenes, jobId, isLoading, activeView = "keyframes" }: VisualCacheProps) {
  const [selectedScene, setSelectedScene] = useState<JobSceneRow | null>(null);
  const [refiningScene, setRefiningScene] = useState<number | null>(null);
  const [refinePrompt, setRefinePrompt] = useState("");
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const approveMutation = useMutation({
    mutationFn: async (sceneNumber: number) => {
      if (!jobId) throw new Error("Job ID missing");
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const apiKey = process.env.NEXT_PUBLIC_API_KEY || "dev-secret-key-123";
      
      const resp = await fetch(`${apiBase}/jobs/${jobId}/scenes/${sceneNumber}/approve`, {
        method: "POST",
        headers: {
          "X-API-Key": apiKey,
          "Content-Type": "application/json",
        },
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Failed to approve scene");
      }
      return resp.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    },
    onError: (error: Error) => {
      console.error("Production Error:", error.message);
      alert(`Production trigger failed: ${error.message}`);
    }
  });

  const handleProduce = (e: React.MouseEvent, sceneNumber: number) => {
    e.stopPropagation();
    approveMutation.mutate(sceneNumber);
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 h-full py-4 overflow-y-auto pr-2 custom-scrollbar">
        {[1, 2, 3, 4].map((i) => (
          <motion.div 
            key={i} 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1, duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
            className="aspect-video bg-white/40 backdrop-blur-[40px] rounded-[2rem] border border-indigo-100/50 relative overflow-hidden flex flex-col items-center justify-center p-8 shadow-sm"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/40 to-indigo-100/20 animate-pulse" />
            
            <div className="relative z-10">
              <div className="w-8 h-8 rounded-full border-2 border-indigo-200 border-t-indigo-500 animate-spin mx-auto mb-3 shadow-[0_0_15px_rgba(99,102,241,0.2)]" />
              <div className="flex flex-col gap-1.5 w-full items-center">
                <div className="h-1.5 w-12 bg-indigo-200/50 rounded-full animate-pulse" />
                <div className="h-1.5 w-8 bg-indigo-200/40 rounded-full animate-pulse" delay-100 />
              </div>
            </div>
            
            <span className="absolute bottom-3 left-0 w-full text-center text-[7px] font-black uppercase tracking-widest text-indigo-400">
              Structuring Scene {i}...
            </span>
          </motion.div>
        ))}
      </div>
    );
  }

  if (scenes.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-12 text-center bg-white/40 backdrop-blur-md rounded-3xl border border-slate-200/60 shadow-[0_8px_32px_-12px_rgba(0,0,0,0.05)] relative overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-100 rounded-full blur-[100px] -z-10 pointer-events-none opacity-50" />
        <div className="bg-indigo-50/80 p-5 rounded-3xl mb-6 shadow-sm border border-indigo-100/50">
          <CameraOff className="text-indigo-400" size={32} />
        </div>
        <p className="text-sm font-black text-slate-900 tracking-widest uppercase mb-2">
          Awaiting Production Blueprints
        </p>
        <p className="text-xs font-semibold text-slate-500 max-w-[250px] leading-relaxed">
          Initialize a new cinematic blueprint in the Production Monitor to begin generating assets.
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full text-white">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 h-full py-4 overflow-y-auto pr-3 custom-scrollbar">
        {scenes.map((scene, i) => {
          const hasAsset = activeView === "keyframes" ? !!scene.keyframe_url : !!scene.motion_url;
          const assetUrl = activeView === "keyframes" ? scene.keyframe_url : scene.motion_url;

          return (
            <motion.div
              key={`${activeView}-${i}`}
              layoutId={`scene-${scene.scene_number}-${activeView}`}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, ease: [0.23, 1, 0.32, 1] }}
              whileHover={{ scale: 1.03, y: -5 }}
              onClick={() => setSelectedScene(scene)}
              className={cn(
                "group relative aspect-video rounded-3xl overflow-hidden cursor-pointer shadow-md hover:shadow-2xl hover:shadow-indigo-500/20 transition-all duration-300 border bg-white",
                !hasAsset ? "border-dashed border-slate-300 bg-slate-50/50" : "border-slate-200"
              )}
            >
              {hasAsset ? (
                <>
                  {activeView === "keyframes" ? (
                    <motion.img
                      src={assetUrl}
                      alt={`Scene ${scene.scene_number}`}
                      initial={{ scale: 1 }}
                      whileHover={{ scale: 1.15, x: -8, y: -5 }}
                      transition={{ duration: 1.2, ease: [0.23, 1, 0.32, 1] }}
                      className="w-full h-full object-cover shadow-inner"
                    />
                  ) : (
                    <motion.div 
                      className="relative w-full h-full overflow-hidden"
                      whileHover={{ scale: 1.05 }}
                      transition={{ duration: 0.8 }}
                    >
                      <video
                        src={assetUrl}
                        muted
                        loop
                        playsInline
                        className="w-full h-full object-cover transition-transform duration-1000 group-hover:scale-125"
                        onMouseOver={(e) => (e.currentTarget as HTMLVideoElement).play()}
                        onMouseOut={(e) => {
                          const v = e.currentTarget as HTMLVideoElement;
                          v.pause();
                          v.currentTime = 0;
                        }}
                      />
                      <div className="absolute inset-0 flex items-center justify-center bg-transparent backdrop-blur-[2px] opacity-0 group-hover:opacity-100 transition-opacity duration-500">
                        <div className="bg-white/90 p-5 rounded-full shadow-2xl transform scale-90 group-hover:scale-100 transition-transform duration-500 hover:bg-white active:scale-95">
                          <Play size={40} className="text-slate-900 fill-slate-900 ml-1" />
                        </div>
                      </div>
                    </motion.div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 flex items-end p-6 md:p-8">
                    <div className="flex justify-between items-end w-full">
                      <div className="flex flex-col gap-2">
                        <span className="text-xs md:text-sm font-black text-white/90 tracking-[0.2em] leading-none mb-1">
                          {activeView === "keyframes" ? "KEYFRAME" : "MOTION"} <span className="text-indigo-400">{scene.scene_number}</span>
                        </span>
                        {activeView === "keyframes" && scene.status !== "APPROVED" && !scene.motion_url && (
                          <button 
                            onClick={(e) => handleProduce(e, scene.scene_number)}
                            disabled={approveMutation.isPending}
                            className="flex items-center gap-2 bg-white text-indigo-900 hover:bg-indigo-50 text-xs font-black py-2.5 px-5 rounded-2xl transition-all shadow-[0_8px_30px_rgba(255,255,255,0.4)] active:scale-95 border border-white"
                          >
                            <Cpu size={16} className="animate-pulse" />
                            PRODUCE VIDEO
                          </button>
                        )}
                        {activeView === "keyframes" && scene.status === "APPROVED" && !scene.motion_url && (
                          <div className="flex items-center gap-2 bg-white/20 backdrop-blur-xl text-white text-xs font-black py-2.5 px-5 rounded-2xl border border-white/20 shadow-lg">
                            <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />
                            RENDERING...
                          </div>
                        )}
                        {scene.motion_url && (
                          <div className="flex items-center gap-2 bg-emerald-500/20 backdrop-blur-xl text-emerald-400 text-xs font-black py-2.5 px-5 rounded-2xl border border-emerald-500/30 shadow-[0_8px_30px_rgba(16,185,129,0.2)]">
                            <CheckCircle2 size={16} />
                            READY FOR MASTER
                          </div>
                        )}
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            setRefiningScene(scene.scene_number);
                            setRefinePrompt("");
                          }}
                          className="flex items-center gap-2 bg-slate-900 border border-slate-700 text-white text-[10px] font-black py-2 px-4 rounded-xl hover:bg-slate-800 transition-all active:scale-95 shadow-xl"
                        >
                          <RefreshCw size={12} className={cn(refiningScene === scene.scene_number && "animate-spin")} />
                          REFINE SHOT
                        </button>
                      </div>
                      <div className="bg-white/20 backdrop-blur-xl p-3 md:p-4 rounded-full mb-1 border border-white/30 transform transition-transform group-hover:scale-110 shadow-xl">
                        <Maximize2 size={24} className="text-white" />
                      </div>
                    </div>
                  </div>

                  {/* --- 🛠️ REFINER OVERLAY --- */}
                  <AnimatePresence>
                    {refiningScene === scene.scene_number && (
                      <motion.div 
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        onClick={(e) => e.stopPropagation()}
                        className="absolute inset-0 z-20 bg-slate-900/90 backdrop-blur-xl p-6 flex flex-col justify-center items-center text-center"
                      >
                         <h4 className="text-white font-black text-sm mb-4 tracking-widest">REFINE SCENE {scene.scene_number}</h4>
                         <textarea 
                           autoFocus
                           value={refinePrompt}
                           onChange={(e) => setRefinePrompt(e.target.value)}
                           placeholder="Rewrite this shot logic..."
                           className="w-full bg-white/10 border border-white/20 rounded-xl p-3 text-white text-xs mb-4 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none h-20"
                         />
                         <div className="flex gap-2 w-full">
                           <button 
                             onClick={() => setRefiningScene(null)}
                             className="flex-1 bg-white/10 hover:bg-white/20 text-white text-[10px] font-black py-3 rounded-xl transition-all"
                           >
                             CANCEL
                           </button>
                           <button 
                             onClick={() => {
                               toast({ title: "Refiner Triggered", description: `Re-architecting Scene ${scene.scene_number}...`, type: "info" });
                               setRefiningScene(null);
                             }}
                             className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-black py-3 rounded-xl shadow-lg transition-all"
                           >
                             REGENERATE
                           </button>
                         </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </>
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center p-8 text-center text-slate-400">
                  <div className="relative mb-6">
                    <div className="absolute inset-0 bg-indigo-500/20 blur-2xl rounded-full" />
                    <div className="w-16 h-16 border-[3px] border-indigo-100/30 border-t-indigo-500 rounded-full animate-spin relative z-10" />
                    <Film className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-indigo-400 z-10" size={24} />
                  </div>
                  <span className="text-xs font-black text-indigo-500 uppercase tracking-[0.2em] animate-pulse bg-indigo-50 px-4 py-2 rounded-xl">
                    Generating {activeView === "motion" ? "Motion Logic" : "Keyframe Composition"}...
                  </span>
                </div>
              )}
              
              <div className="absolute top-6 left-6 bg-slate-900/40 backdrop-blur-2xl border border-slate-700/50 text-xs text-white px-4 py-2 rounded-xl font-black tracking-widest shadow-xl flex items-center gap-2">
                {activeView === "motion" && <Film size={14} className="text-indigo-400" />}
                SCENE {scene.scene_number}
              </div>

              {/* --- 📡 PRO TELEMETRY HUD --- */}
              <div className="absolute top-4 right-4 flex flex-col gap-1.5 items-end pointer-events-none opacity-0 group-hover:opacity-100 transition-all duration-500 translate-x-4 group-hover:translate-x-0">
                {scene.lighting_prompt && (
                  <div className="bg-black/60 backdrop-blur-2xl border border-white/10 px-2.5 py-1.5 rounded-xl flex items-center gap-2 shadow-2xl">
                    <div className="w-1.5 h-1.5 bg-amber-400 rounded-full shadow-[0_0_8px_rgba(251,191,36,0.8)]" />
                    <span className="text-[9px] font-black tracking-[0.1em] text-white/90 uppercase">HDR LIGHT: {scene.light_source_origin || "RAY-TRACED"}</span>
                  </div>
                )}
                {scene.spatial_layout && (
                  <div className="bg-black/60 backdrop-blur-2xl border border-white/10 px-2.5 py-1.5 rounded-xl flex items-center gap-2 shadow-2xl">
                    <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
                    <span className="text-[9px] font-black tracking-[0.1em] text-white/90 uppercase">SPATIAL: {scene.spatial_layout.split(',')[0]}</span>
                  </div>
                )}
                {scene.motion_intensity && (
                  <div className="bg-black/60 backdrop-blur-2xl border border-white/10 px-2.5 py-1.5 rounded-xl flex items-center gap-2 shadow-2xl">
                    <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(129,140,248,0.8)]" />
                    <span className="text-[9px] font-black tracking-[0.1em] text-white/90 uppercase">MOTION INTENSITY: {scene.motion_intensity}</span>
                  </div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Lightbox Modal */}
      <AnimatePresence>
        {selectedScene && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[110] flex items-center justify-center p-4 md:p-8 bg-slate-900/60 backdrop-blur-3xl"
            onClick={() => setSelectedScene(null)}
          >
            <motion.div
              layoutId={`scene-${selectedScene.scene_number}-${activeView}`}
              className="relative max-w-[85vw] max-h-[85vh] w-full aspect-video bg-black rounded-[2.5rem] overflow-hidden shadow-[0_32px_128px_-16px_rgba(0,0,0,0.8)] border border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              {(activeView === "keyframes" ? selectedScene.keyframe_url : selectedScene.motion_url) ? (
                activeView === "keyframes" ? (
                  <img
                    src={selectedScene.keyframe_url}
                    alt={`Scene ${selectedScene.scene_number}`}
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <video
                    src={selectedScene.motion_url}
                    controls
                    autoPlay
                    loop
                    className="w-full h-full object-contain"
                  />
                )
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-white p-12">
                   <div className="w-20 h-20 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-6" />
                   <h3 className="text-xl font-bold uppercase tracking-widest text-indigo-400 animate-pulse">Asset Under Construction</h3>
                   <p className="text-slate-400 text-sm mt-2">The 11-agent pipeline is currently rendering this asset.</p>
                </div>
              )}
              
              {/* Overlay Controls */}
              <div className="absolute top-0 left-0 w-full p-8 flex justify-between items-start bg-gradient-to-b from-black/80 to-transparent">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="bg-indigo-500 w-2 h-2 rounded-full animate-pulse" />
                    <span className="text-[10px] font-black uppercase text-indigo-400 tracking-widest">
                      {activeView === "keyframes" ? "Primary Keyframe" : "High-Fidelity Motion"}
                    </span>
                  </div>
                  <h3 className="text-white font-black text-3xl tracking-tight">SCENE <span className="text-indigo-400">{selectedScene.scene_number}</span></h3>
                </div>
                <button 
                  onClick={() => setSelectedScene(null)}
                  className="bg-white/10 hover:bg-white/20 backdrop-blur-md p-4 rounded-3xl text-white transition-all active:scale-95 border border-white/10"
                >
                  <X size={28} />
                </button>
              </div>

              <div className="absolute bottom-0 left-0 w-full p-8 flex justify-between items-end bg-gradient-to-t from-black via-black/50 to-transparent">
                <div className="flex gap-4">
                  <button className="group relative flex items-center gap-3 bg-white text-slate-900 px-8 py-4 rounded-2xl text-sm font-black shadow-[0_0_30px_rgba(255,255,255,0.3)] hover:scale-105 transition-all active:scale-95 focus:outline-none">
                    <Download size={18} className="group-hover:-translate-y-0.5 transition-transform" />
                    DOWNLOAD ASSET
                  </button>
                  <button className="group flex items-center gap-3 bg-white/10 hover:bg-white/20 backdrop-blur-xl px-8 py-4 rounded-2xl text-white text-sm font-bold border border-white/20 transition-all hover:scale-105 active:scale-95 focus:outline-none">
                    <ExternalLink size={18} />
                    EXPORT TO MASTER
                  </button>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <div className="flex items-center gap-2 px-4 py-2 bg-indigo-600/20 backdrop-blur-md border border-indigo-500/30 rounded-xl">
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.8)]" />
                    <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Verified Production</span>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #e2e8f0;
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #cbd5e1;
        }
      `}</style>
    </div>
  );
}
