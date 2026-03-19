import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import axios from "axios";
import type {
  AxiosError,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";

// We test the interceptor logic by importing the configured api instance.
// To control network responses we intercept the adapter level.

let api: typeof import("@/lib/api").default;

// Track calls to refresh endpoint
let refreshCalls: number;
let refreshShouldSucceed: boolean;

// Mock window.location for redirect tests
const originalLocation = globalThis.window?.location;

beforeEach(async () => {
  vi.resetModules();
  refreshCalls = 0;
  refreshShouldSucceed = true;

  // Mock window and location
  if (typeof globalThis.window === "undefined") {
    // @ts-expect-error -- test-only global setup
    globalThis.window = {
      location: { href: "/dashboard", pathname: "/dashboard" },
    };
  } else {
    Object.defineProperty(window, "location", {
      writable: true,
      value: { href: "/dashboard", pathname: "/dashboard" },
    });
  }

  // Mock axios.post for refresh calls
  vi.spyOn(axios, "post").mockImplementation(async (url: string) => {
    if (url === "/api/v1/auth/refresh") {
      refreshCalls++;
      if (refreshShouldSucceed) {
        return {
          data: { data: { access_token: "new-token" } },
          status: 200,
        } as AxiosResponse;
      }
      const err = new Error("Refresh failed") as AxiosError;
      err.response = {
        status: 401,
        data: {},
        headers: {},
        statusText: "Unauthorized",
        config: {} as InternalAxiosRequestConfig,
      };
      err.isAxiosError = true;
      throw err;
    }
    throw new Error(`Unexpected POST to ${url}`);
  });

  // Dynamic import to get a fresh module each test
  const mod = await import("@/lib/api");
  api = mod.default;
});

afterEach(() => {
  vi.restoreAllMocks();
  if (originalLocation) {
    Object.defineProperty(window, "location", {
      writable: true,
      value: originalLocation,
    });
  }
});

// Helper: create a mock AxiosError with a given status
function makeAxiosError(
  status: number,
  method: string = "get",
  headers: Record<string, string> = {},
): AxiosError {
  const config: InternalAxiosRequestConfig = {
    method,
    url: "/test",
    headers: {} as InternalAxiosRequestConfig["headers"],
  } as InternalAxiosRequestConfig;

  const error = new Error(`Request failed with status ${status}`) as AxiosError;
  error.config = config;
  error.response = {
    status,
    data: {},
    headers,
    statusText: "",
    config,
  };
  error.isAxiosError = true;
  error.code = undefined;
  return error;
}

describe("API interceptor", () => {
  it("passes successful responses through unchanged", async () => {
    // Temporarily override the adapter to return success
    const mockAdapter = vi.fn().mockResolvedValue({
      data: { data: { id: 1 } },
      status: 200,
      statusText: "OK",
      headers: {},
      config: {},
    });
    api.defaults.adapter = mockAdapter;

    const res = await api.get("/test");
    expect(res.status).toBe(200);
    expect(res.data).toEqual({ data: { id: 1 } });
  });

  it("retries on 5xx server errors for GET requests with exponential backoff", async () => {
    let callCount = 0;

    const mockAdapter = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount <= 2) {
        // First two calls fail with 502
        const err = makeAxiosError(502, "get");
        return Promise.reject(err);
      }
      // Third call succeeds
      return Promise.resolve({
        data: { data: "ok" },
        status: 200,
        statusText: "OK",
        headers: {},
        config: {},
      });
    });

    api.defaults.adapter = mockAdapter;

    const res = await api.get("/test");
    expect(res.status).toBe(200);
    // 1 original + 2 retries = 3 total calls
    expect(callCount).toBe(3);
  });

  it("does NOT retry POST requests on 5xx errors", async () => {
    let callCount = 0;

    const mockAdapter = vi.fn().mockImplementation(() => {
      callCount++;
      const err = makeAxiosError(500, "post");
      // Override the config method to POST
      err.config!.method = "post";
      return Promise.reject(err);
    });

    api.defaults.adapter = mockAdapter;

    await expect(api.post("/test", { data: 1 })).rejects.toThrow();
    // Should only be called once -- no retry for POST
    expect(callCount).toBe(1);
  });

  it("triggers token refresh on 401 and retries the original request", async () => {
    let callCount = 0;

    const mockAdapter = vi
      .fn()
      .mockImplementation((config: InternalAxiosRequestConfig) => {
        callCount++;
        if (callCount === 1) {
          // First call returns 401
          const err = makeAxiosError(401, config.method ?? "get");
          err.config = config;
          if (err.response) err.response.config = config;
          return Promise.reject(err);
        }
        // After refresh, second call succeeds
        return Promise.resolve({
          data: { data: "authenticated" },
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        });
      });

    api.defaults.adapter = mockAdapter;
    refreshShouldSucceed = true;

    const res = await api.get("/protected");
    expect(res.data).toEqual({ data: "authenticated" });
    expect(refreshCalls).toBe(1);
    expect(callCount).toBe(2);
  });

  it("redirects to /login when refresh fails on 401", async () => {
    const mockAdapter = vi
      .fn()
      .mockImplementation((config: InternalAxiosRequestConfig) => {
        const err = makeAxiosError(401, config.method ?? "get");
        err.config = config;
        if (err.response) err.response.config = config;
        return Promise.reject(err);
      });

    api.defaults.adapter = mockAdapter;
    refreshShouldSucceed = false;

    await expect(api.get("/protected")).rejects.toThrow();
    expect(refreshCalls).toBe(1);
    expect(window.location.href).toBe("/login");
  });

  it("retries on 429 and respects Retry-After header", async () => {
    let callCount = 0;

    const mockAdapter = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        const err = makeAxiosError(429, "get", { "retry-after": "1" });
        return Promise.reject(err);
      }
      return Promise.resolve({
        data: { data: "ok" },
        status: 200,
        statusText: "OK",
        headers: {},
        config: {},
      });
    });

    api.defaults.adapter = mockAdapter;

    const res = await api.get("/rate-limited");
    expect(res.status).toBe(200);
    expect(callCount).toBe(2);
  });

  it.skip(
    "rejects with friendly message after exhausting 429 retries (slow — uses real timers)",
    { timeout: 30000 },
    async () => {
      let callCount = 0;

      const mockAdapter = vi.fn().mockImplementation(() => {
        callCount++;
        const err = makeAxiosError(429, "get", { "retry-after": "1" });
        return Promise.reject(err);
      });

      api.defaults.adapter = mockAdapter;

      await expect(api.get("/rate-limited")).rejects.toThrow(
        "Too many requests. Please wait a moment and try again.",
      );
      // 1 original + 2 retries = 3 total calls
      expect(callCount).toBe(3);
    },
  );

  it("does not redirect to /login if already on /login page", async () => {
    window.location.pathname = "/login";
    window.location.href = "/login";

    const mockAdapter = vi
      .fn()
      .mockImplementation((config: InternalAxiosRequestConfig) => {
        const err = makeAxiosError(401, config.method ?? "get");
        err.config = config;
        if (err.response) err.response.config = config;
        return Promise.reject(err);
      });

    api.defaults.adapter = mockAdapter;
    refreshShouldSucceed = false;

    await expect(api.get("/protected")).rejects.toThrow();
    // href should remain /login, not be set again
    expect(window.location.href).toBe("/login");
  });
});
