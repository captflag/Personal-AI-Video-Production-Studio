"use client";

import { useFormState, useFormStatus } from "react-dom";
import { loginAction } from "@/app/login/actions";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Lock, Loader2, AlertCircle, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface FormState {
  error: Record<string, string[] | undefined>;
}

const initialState: FormState = {
  error: {},
};

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className={cn(
        "w-full h-14 bg-slate-900 text-white rounded-2xl font-bold tracking-wide transition-all",
        "hover:bg-slate-800 active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed",
        "flex items-center justify-center gap-2 shadow-xl shadow-slate-200"
      )}
    >
      {pending ? (
        <Loader2 className="w-5 h-5 animate-spin" />
      ) : (
        <>
          <Sparkles className="w-4 h-4 mr-2" />
          Access Studio
        </>
      )}
    </button>
  );
}

export function LoginForm() {
  const [state, formAction] = useFormState<FormState, FormData>(
    loginAction as (state: FormState, formData: FormData) => Promise<FormState>,
    initialState
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 25, stiffness: 200 }}
      className="w-full max-w-md mx-auto"
    >
      <div className="glass-card p-8 md:p-12 rounded-[2.5rem] shadow-[0_40px_100px_-20px_rgba(0,0,0,0.05)] border border-white/50 bg-white/40 backdrop-blur-3xl relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-indigo-500 via-sky-400 to-indigo-500" />
        <div className="mb-10 text-center">
          <div className="inline-flex items-center gap-2 mb-4 bg-indigo-50/80 border border-indigo-100/50 px-3 py-1.5 rounded-xl">
            <Sparkles className="w-3 h-3 text-indigo-600" />
            <span className="text-[10px] font-black uppercase text-indigo-600 tracking-widest leading-none mt-0.5">Authentication Gateway</span>
          </div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-2">Welcome Back</h1>
          <p className="text-slate-500 text-sm font-medium">Enter your credentials to enter the studio.</p>
        </div>

        <form action={formAction} className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase text-slate-400 tracking-widest ml-4">Email Address</label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-5 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-600 transition-colors">
                <Mail size={18} />
              </div>
              <input
                name="email"
                type="email"
                placeholder="admin@studio.ai"
                className={cn(
                  "w-full h-14 bg-white/50 border border-slate-200 rounded-2xl pl-14 pr-6 text-sm font-medium transition-all",
                  "focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none",
                  state.error?.email ? "border-red-500 focus:ring-red-500/10 focus:border-red-500" : ""
                )}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase text-slate-400 tracking-widest ml-4">Password</label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-5 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-600 transition-colors">
                <Lock size={18} />
              </div>
              <input
                name="password"
                type="password"
                placeholder="••••••••"
                className={cn(
                  "w-full h-14 bg-white/50 border border-slate-200 rounded-2xl pl-14 pr-6 text-sm font-medium transition-all",
                  "focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none",
                  state.error?.password ? "border-red-500 focus:ring-red-500/10 focus:border-red-500" : ""
                )}
              />
            </div>
          </div>

          <AnimatePresence mode="wait">
            {state.error?.form && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="p-4 bg-red-50 border border-red-100 rounded-2xl flex items-center gap-3"
              >
                <AlertCircle className="text-red-500 shrink-0" size={18} />
                <p className="text-[10px] font-bold text-red-600 leading-tight">{state.error.form[0]}</p>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="pt-2">
            <SubmitButton />
          </div>
        </form>

        <div className="mt-10 pt-8 border-t border-slate-100 text-center">
          <p className="text-xs font-medium text-slate-400">Internal Access Only | ZeroGPU Studio</p>
        </div>
      </div>
    </motion.div>
  );
}
