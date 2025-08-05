import api from "./api";

interface ErrorReport {
  message: string;
  stack?: string;
  component?: string;
  url?: string;
  user_agent?: string;
}

const REPORT_ENDPOINT = "/client-errors";
const MAX_REPORTS_PER_MINUTE = 10;

let reportCount = 0;
let resetTimer: ReturnType<typeof setTimeout> | null = null;

export function reportError(error: Error | string, component?: string): void {
  if (reportCount >= MAX_REPORTS_PER_MINUTE) return;
  reportCount++;

  if (!resetTimer) {
    resetTimer = setTimeout(() => {
      reportCount = 0;
      resetTimer = null;
    }, 60_000);
  }

  const report: ErrorReport = {
    message: typeof error === "string" ? error : error.message,
    stack: typeof error === "string" ? undefined : error.stack,
    component,
    url: typeof window !== "undefined" ? window.location.href : undefined,
    user_agent:
      typeof navigator !== "undefined" ? navigator.userAgent : undefined,
  };

  // Fire-and-forget, don't block UI
  api.post(REPORT_ENDPOINT, report).catch(() => {
    // Silently ignore reporting failures
  });
}

export function installGlobalErrorHandlers(): void {
  if (typeof window === "undefined") return;

  window.addEventListener("error", (event) => {
    reportError(event.error ?? event.message, "window.onerror");
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason =
      event.reason instanceof Error ? event.reason : String(event.reason);
    reportError(
      reason instanceof Error ? reason : new Error(String(reason)),
      "unhandledrejection",
    );
  });
}
