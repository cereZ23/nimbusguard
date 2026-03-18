/**
 * Extract a human-readable error message from an unknown error.
 * Handles Axios errors, standard Error objects, and arbitrary values.
 */
export function extractApiError(err: unknown): string {
  if (err && typeof err === "object") {
    // Axios error with response
    const axiosErr = err as {
      response?: { data?: { detail?: string; error?: string } };
      message?: string;
    };
    if (axiosErr.response?.data?.detail) {
      return axiosErr.response.data.detail;
    }
    if (axiosErr.response?.data?.error) {
      return axiosErr.response.data.error;
    }
    if (axiosErr.message) {
      return axiosErr.message;
    }
  }
  if (typeof err === "string") {
    return err;
  }
  return "An unexpected error occurred";
}
