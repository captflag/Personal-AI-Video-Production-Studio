"use client";
import { createContext, useContext, useState, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, X, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastType = "success" | "error" | "info" | "agent";

interface ToastProps {
  id: string;
  title: string;
  description?: string;
  type: ToastType;
}

interface ToastContextType {
  toast: (payload: Omit<ToastProps, "id">) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastProps[]>([]);

  const toast = (payload: Omit<ToastProps, "id">) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { ...payload, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const getIcon = (type: ToastType) => {
    switch (type) {
      case "success": return <CheckCircle2 size={18} className="text-emerald-500" />;
      case "error": return <AlertTriangle size={18} className="text-rose-500" />;
      case "agent": return <Sparkles size={18} className="text-indigo-500" />;
      default: return <Info size={18} className="text-sky-500" />;
    }
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[200] flex flex-col gap-3 pointer-events-none">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 50, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95, filter: "blur(4px)" }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
              className="pointer-events-auto w-80 bg-white/70 backdrop-blur-2xl border border-slate-200 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.1)] rounded-2xl p-4 flex gap-3 items-start relative overflow-hidden"
            >
              <div className={cn(
                "absolute top-0 left-0 w-1 h-full",
                t.type === "success" ? "bg-emerald-500" :
                t.type === "error" ? "bg-rose-500" :
                t.type === "agent" ? "bg-indigo-500" : "bg-sky-500"
              )} />
              <div className="mt-0.5">{getIcon(t.type)}</div>
              <div className="flex-1">
                <h4 className="text-sm font-bold text-slate-900 tracking-tight leading-tight">{t.title}</h4>
                {t.description && <p className="text-xs font-semibold text-slate-500 mt-1 leading-relaxed">{t.description}</p>}
              </div>
              <button 
                onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))} 
                className="text-slate-400 hover:text-slate-900 transition-colors bg-slate-100/50 p-1 rounded-full"
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
};
