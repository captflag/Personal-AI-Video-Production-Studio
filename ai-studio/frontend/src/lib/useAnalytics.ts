"use client";
import { useCallback } from "react";

export type EventType = "job_started" | "job_completed" | "scene_approved" | "asset_downloaded" | "tab_switched" | "error_caught" | "visual_mode_toggled";

export function useAnalytics() {
  const trackEvent = useCallback((eventName: EventType, metadata: Record<string, unknown> = {}) => {
    // In a production growth engine, this batches and transmits to Mixpanel/PostHog.
    // For now, it logs to the console to simulate business intelligence gathering without blocking the main thread.
    const payload = {
      event: eventName,
      timestamp: new Date().toISOString(),
      userAgent: typeof window !== "undefined" ? navigator.userAgent : "ssr",
      url: typeof window !== "undefined" ? window.location.href : "",
      ...metadata,
    };
    
    console.groupCollapsed(`📈 [Growth Engines]: ${eventName}`);
    console.info("Event tracking batched. Metadata:");
    console.dir(payload);
    console.groupEnd();
    
    // Example: fetch('/api/telemetry', { method: 'POST', body: JSON.stringify(payload) })
  }, []);

  return { trackEvent };
}
