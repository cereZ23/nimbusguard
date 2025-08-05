import axios from "axios";
import type { AxiosError } from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// Retry configuration for server errors and network failures
const MAX_RETRIES = 2;
const RETRY_BASE_DELAY_MS = 1000;
const RETRYABLE_STATUS_CODES = new Set([500, 502, 503, 504]);

// Rate limit (429) retry configuration
const MAX_429_RETRIES = 2;
const DEFAULT_RETRY_AFTER_SECONDS = 10;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Track refresh in progress to avoid concurrent attempts
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  try {
    // Cookie is sent automatically via withCredentials
    await axios.post("/api/v1/auth/refresh", {}, { withCredentials: true });
    return true;
  } catch {
    // Refresh failed
    return false;
  }
}

// Response interceptor: retry on 5xx / network errors, then token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;
    if (!originalRequest) {
      return Promise.reject(error);
    }

    const configRecord = originalRequest as unknown as Record<string, unknown>;

    // --- Retry logic for 5xx and network errors (non-POST only) ---
    const isServerError =
      error.response && RETRYABLE_STATUS_CODES.has(error.response.status);
    const isNetworkError = !error.response && error.code !== "ERR_CANCELED";
    const isRetryable =
      (isServerError || isNetworkError) &&
      originalRequest.method?.toUpperCase() !== "POST";

    if (isRetryable) {
      const retryCount = (configRecord._retryCount as number) ?? 0;
      if (retryCount < MAX_RETRIES) {
        configRecord._retryCount = retryCount + 1;
        const delay = RETRY_BASE_DELAY_MS * Math.pow(2, retryCount); // 1s, 2s
        await sleep(delay);
        return api(originalRequest);
      }
    }

    // --- Rate limit retry on 429 ---
    if (error.response?.status === 429) {
      const retryCount429 = (configRecord._retryCount429 as number) ?? 0;
      if (retryCount429 < MAX_429_RETRIES) {
        configRecord._retryCount429 = retryCount429 + 1;
        const retryAfterHeader = error.response.headers?.["retry-after"];
        const retryAfterSeconds = retryAfterHeader
          ? parseInt(String(retryAfterHeader), 10)
          : DEFAULT_RETRY_AFTER_SECONDS;
        const delayMs =
          (Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0
            ? retryAfterSeconds
            : DEFAULT_RETRY_AFTER_SECONDS) * 1000;
        await sleep(delayMs);
        return api(originalRequest);
      }
      // All 429 retries exhausted — reject with user-friendly message
      return Promise.reject(
        new Error("Too many requests. Please wait a moment and try again."),
      );
    }

    // --- Token refresh on 401 ---
    if (
      error.response?.status === 401 &&
      typeof window !== "undefined" &&
      !configRecord._retry
    ) {
      configRecord._retry = true;

      if (!isRefreshing) {
        isRefreshing = true;
        refreshPromise = tryRefresh().finally(() => {
          isRefreshing = false;
          refreshPromise = null;
        });
      }

      const refreshed = await refreshPromise;
      if (refreshed) {
        // Retry the original request -- cookies are now updated
        return api(originalRequest);
      }

      // Refresh failed -- redirect to login
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default api;
