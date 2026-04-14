"use client";

import { useEffect, useRef } from "react";
import { Clock, X } from "lucide-react";
import { useAuth } from "@/lib/auth";

const AUTO_DISMISS_MS = 30_000;

export default function SessionWarning() {
  const { showSessionWarning, extendSession, dismissSessionWarning } =
    useAuth();
  const autoDismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  // Auto-dismiss after 30 seconds if the user does not interact
  useEffect(() => {
    if (!showSessionWarning) {
      return;
    }

    autoDismissTimerRef.current = setTimeout(() => {
      dismissSessionWarning();
    }, AUTO_DISMISS_MS);

    return () => {
      if (autoDismissTimerRef.current !== null) {
        clearTimeout(autoDismissTimerRef.current);
        autoDismissTimerRef.current = null;
      }
    };
  }, [showSessionWarning, dismissSessionWarning]);

  if (!showSessionWarning) {
    return null;
  }

  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-3 border-b border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-950/60"
    >
      <div className="flex items-center gap-2.5">
        <Clock
          size={18}
          className="shrink-0 text-amber-600 dark:text-amber-400"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
          Your session expires in 2 minutes.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={extendSession}
          className="rounded-md bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1 dark:bg-amber-500 dark:hover:bg-amber-600 dark:focus:ring-offset-gray-900"
        >
          Extend Session
        </button>
        <button
          onClick={dismissSessionWarning}
          className="rounded-md p-1 text-amber-600 transition-colors hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500 dark:text-amber-400 dark:hover:bg-amber-900/50"
          aria-label="Dismiss session warning"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
