import { useEffect, useRef, useState } from "react";
import { Terminal, Activity, ChevronDown, ChevronRight, Cpu } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface LogEntry {
  id: string;
  agent: string;
  message: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export const StatusConsole = ({ logs }: { logs: LogEntry[] }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);

  useEffect(() => {
    if (scrollRef.current && !expandedLog) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, expandedLog]);

  return (
    <div className="h-full flex flex-col font-mono text-[10px] sm:text-xs">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-indigo-100/30">
        <div className="flex items-center gap-2 text-indigo-600 bg-indigo-50/50 px-3 py-1.5 rounded-xl border border-indigo-100/50 shadow-sm">
          <Terminal size={14} />
          <span className="font-black uppercase tracking-widest text-[10px]">Orchestrator_v1.0</span>
        </div>
        <div className="flex items-center gap-2 text-emerald-600 bg-emerald-50/80 px-3 py-1.5 rounded-xl shadow-sm border border-emerald-100/50">
          <Activity size={12} className="animate-pulse" />
          <span className="font-black tracking-widest text-[10px]">LIVE</span>
        </div>
      </div>
      
      <div 
        ref={scrollRef} 
        className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar rounded-xl bg-slate-900/5 p-2 border border-slate-900/5 shadow-[inset_0_2px_10px_rgba(0,0,0,0.02)]"
      >
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 opacity-60">
            <Cpu size={24} className="mb-2" />
            <div className="italic font-medium text-center leading-relaxed max-w-[150px]">Awaiting multi-agent initialization...</div>
          </div>
        ) : (
          logs.map((log) => {
            const isExpanded = expandedLog === log.id;
            const hasData = log.message.includes("{") || log.payload;
            return (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                key={log.id}
                className={cn(
                  "group relative overflow-hidden transition-all duration-300 rounded-xl border p-2",
                  isExpanded ? "bg-white shadow-md border-indigo-100" : "bg-white/40 hover:bg-white/80 border-transparent shadow-sm hover:shadow"
                )}
              >
                <div 
                  className={cn("flex gap-3 items-start", hasData ? "cursor-pointer" : "")}
                  onClick={() => hasData && setExpandedLog(isExpanded ? null : log.id)}
                >
                  <div className="bg-slate-100 text-slate-400 shrink-0 px-2 py-1 rounded-lg border border-slate-200/50 text-[9px] shadow-inner font-bold flex items-center gap-1.5 mt-0.5">
                    {hasData && (
                      isExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />
                    )}
                    {log.timestamp}
                  </div>
                  <div className="flex-1 leading-relaxed mt-0.5">
                    <span className="text-indigo-600 font-bold bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100 mr-2 text-[10px]">
                      {log.agent}
                    </span>
                    <span className="text-slate-700 font-medium group-hover:text-slate-900 transition-colors">
                      {log.message.replace(/\{.*\}/,' { ... }')}
                    </span>
                  </div>
                </div>

                <AnimatePresence>
                  {isExpanded && hasData && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="mt-3 bg-slate-900 text-green-400 p-3 rounded-xl border border-slate-800 shadow-inner overflow-x-auto"
                    >
                      <pre className="text-[9px] sm:text-[10px] m-0 font-mono tracking-wider">
                        {log.payload ? JSON.stringify(log.payload, null, 2) : "{\n  \"action\": \"executing_tool\",\n  \"status\": \"processing\"\n}"}
                      </pre>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
};
