import { LoginForm } from "@/components/LoginForm";
import { LoginVisual } from "@/components/LoginVisual";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Identity Gateway | ZeroGPU Studio",
  description: "Secure entry point for the ZeroGPU multi-agent AI production suite.",
};

export default function LoginPage() {
  return (
    <main className="relative min-h-screen flex items-center justify-center p-6 overflow-hidden">
      <LoginVisual />
      <div className="relative z-50 w-full flex justify-center">
        <LoginForm />
      </div>
      <div className="fixed top-12 left-12 z-20 hidden md:block">
        <div className="flex items-center gap-3">
          <div className="bg-slate-900 p-2 rounded-xl text-white">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
          </div>
          <span className="text-sm font-black tracking-tighter text-slate-900">ZeroGPU Studio</span>
        </div>
      </div>
      <div className="fixed bottom-12 right-12 z-20 hidden md:flex items-center gap-8 text-[10px] font-black uppercase text-slate-400 tracking-widest">
        <span>v.2.4.0-STAGE</span>
        <span>Secure Session (AES-256)</span>
      </div>
    </main>
  );
}
