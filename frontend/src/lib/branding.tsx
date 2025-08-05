"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";
import api from "@/lib/api";
import type { TenantBranding } from "@/types";

const DEFAULT_BRANDING: TenantBranding = {
  logo_url: null,
  primary_color: "#6366f1",
  company_name: "CSPM",
  favicon_url: null,
};

interface BrandingContextType {
  branding: TenantBranding;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

const BrandingContext = createContext<BrandingContextType>({
  branding: DEFAULT_BRANDING,
  isLoading: true,
  refresh: async () => {},
});

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<TenantBranding>(DEFAULT_BRANDING);
  const [isLoading, setIsLoading] = useState(true);

  const fetchBranding = useCallback(async () => {
    try {
      const res = await api.get("/branding");
      const data = res.data?.data as TenantBranding | null;
      if (data) {
        setBranding(data);
      }
    } catch {
      // If fetch fails (e.g. not authenticated yet), keep defaults
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBranding();
  }, [fetchBranding]);

  // Apply CSS custom property for the primary color so components can use it
  useEffect(() => {
    document.documentElement.style.setProperty(
      "--branding-primary",
      branding.primary_color,
    );
  }, [branding.primary_color]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    await fetchBranding();
  }, [fetchBranding]);

  return (
    <BrandingContext.Provider value={{ branding, isLoading, refresh }}>
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding(): BrandingContextType {
  return useContext(BrandingContext);
}
