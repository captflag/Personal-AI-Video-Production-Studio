"use client";
import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertCircle } from "lucide-react";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn("WebGL/Canvas gracefully degraded:", error);
  }

  public render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-50/50 via-white to-sky-50/50 flex flex-col items-center justify-center p-8 text-center -z-20 pointer-events-none">
           {/* Fallback styling that fits the aesthetic but requires no WebGL */}
           <div className="w-[120%] h-[120%] absolute -top-10 -left-10 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-200/40 via-white/10 to-transparent blur-3xl" />
        </div>
      );
    }
    return this.props.children;
  }
}
