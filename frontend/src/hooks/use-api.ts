import useSWR from "swr";
import useSWRMutation from "swr/mutation";
import api from "@/lib/api";

/**
 * Generic hook for paginated list endpoints.
 *
 * Builds a stable string key from the endpoint + params so SWR can
 * deduplicate and cache correctly.
 */
export function useApiList<T>(
  endpoint: string | null,
  params?: Record<string, string | number | undefined>,
) {
  let key: string | null = null;
  if (endpoint !== null) {
    const searchParams = new URLSearchParams();
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== "") {
          searchParams.set(k, String(v));
        }
      }
    }
    const qs = searchParams.toString();
    key = qs ? `${endpoint}?${qs}` : endpoint;
  }

  const { data, error, isLoading, mutate } = useSWR(key);

  return {
    data: (data?.data ?? []) as T[],
    total: (data?.meta?.total ?? 0) as number,
    page: (data?.meta?.page ?? 1) as number,
    size: (data?.meta?.size ?? 20) as number,
    error: error?.message ?? data?.error ?? null,
    isLoading,
    mutate,
  };
}

/**
 * Generic hook for a single resource detail endpoint.
 *
 * Pass `null` as endpoint to conditionally skip the request.
 */
export function useApiDetail<T>(endpoint: string | null) {
  const { data, error, isLoading, mutate } = useSWR(endpoint);

  return {
    data: (data?.data ?? null) as T | null,
    error: error?.message ?? data?.error ?? null,
    isLoading,
    mutate,
  };
}

/**
 * Hook for mutations (POST / PUT / DELETE).
 *
 * Uses SWR mutation so the caller can trigger imperatively
 * and then call `mutate()` on related keys to revalidate caches.
 */
export function useApiMutation<T>(
  endpoint: string,
  method: "post" | "put" | "delete" = "post",
) {
  return useSWRMutation<T, Error, string, unknown>(
    endpoint,
    async (url: string, { arg }: { arg: unknown }) => {
      const res = await api[method](url, arg as Record<string, unknown>);
      return res.data as T;
    },
  );
}
