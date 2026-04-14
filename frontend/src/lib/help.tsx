"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

interface HelpContextValue {
  activeTour: string | null;
  startTour: (tourId: string) => void;
  endTour: () => void;
  isTourCompleted: (tourId: string) => boolean;
  resetTour: (tourId: string) => void;
}

const HelpContext = createContext<HelpContextValue | null>(null);

export function HelpProvider({ children }: { children: React.ReactNode }) {
  const [activeTour, setActiveTour] = useState<string | null>(null);

  const startTour = useCallback((tourId: string) => {
    setActiveTour(tourId);
  }, []);

  const endTour = useCallback(() => {
    setActiveTour(null);
  }, []);

  const isTourCompleted = useCallback((tourId: string) => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(`tour-completed-${tourId}`) === "true";
  }, []);

  const resetTour = useCallback((tourId: string) => {
    localStorage.removeItem(`tour-completed-${tourId}`);
  }, []);

  const value = useMemo(
    () => ({ activeTour, startTour, endTour, isTourCompleted, resetTour }),
    [activeTour, startTour, endTour, isTourCompleted, resetTour],
  );

  return <HelpContext.Provider value={value}>{children}</HelpContext.Provider>;
}

export function useHelp() {
  const ctx = useContext(HelpContext);
  if (!ctx) throw new Error("useHelp must be used within HelpProvider");
  return ctx;
}
