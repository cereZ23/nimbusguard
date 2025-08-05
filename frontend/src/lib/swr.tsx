"use client";

import { SWRConfig } from "swr";
import type { SWRConfiguration } from "swr";
import type { ReactNode } from "react";
import api from "./api";

/**
 * Generic fetcher that works with the API envelope { data, error, meta }.
 * Returns the raw envelope so hooks can destructure data/meta/error.
 */
export const fetcher = async (url: string) => {
  const res = await api.get(url);
  return res.data;
};

/** Default SWR configuration shared across the app. */
export const swrConfig: SWRConfiguration = {
  fetcher,
  revalidateOnFocus: false,
  revalidateOnReconnect: true,
  dedupingInterval: 5000,
  errorRetryCount: 2,
};

/** Client-side SWR provider wrapping children with default config. */
export function SWRProvider({ children }: { children: ReactNode }) {
  return <SWRConfig value={swrConfig}>{children}</SWRConfig>;
}
