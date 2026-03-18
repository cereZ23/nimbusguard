"use client";

import { useState } from "react";
import useSWR from "swr";
import { Copy, Key, Plus, Trash2, X } from "lucide-react";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type { ApiKey, ApiKeyCreated } from "@/types";

const ALLOWED_SCOPES = ["read", "write", "scan"];

export default function ApiKeysPage() {
  const {
    data: apiKeysEnvelope,
    error: apiKeysError,
    isLoading: apiKeysLoading,
    mutate: mutateApiKeys,
  } = useSWR("/api-keys");

  const apiKeys = (apiKeysEnvelope?.data ?? []) as ApiKey[];
  const error = apiKeysError?.message ?? apiKeysEnvelope?.error ?? null;

  const [actionError, setActionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [apiKeyForm, setApiKeyForm] = useState({
    name: "",
    scopes: ["read"] as string[],
    expires_in_days: "" as string,
  });
  const [createdApiKey, setCreatedApiKey] = useState<ApiKeyCreated | null>(
    null,
  );
  const [copiedKey, setCopiedKey] = useState(false);

  const handleCreateApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      const payload: {
        name: string;
        scopes: string[];
        expires_in_days?: number;
      } = {
        name: apiKeyForm.name,
        scopes: apiKeyForm.scopes,
      };
      if (apiKeyForm.expires_in_days) {
        payload.expires_in_days = parseInt(apiKeyForm.expires_in_days, 10);
      }
      const res = await api.post("/api-keys", payload);
      setCreatedApiKey(res.data.data as ApiKeyCreated);
      setApiKeyForm({ name: "", scopes: ["read"], expires_in_days: "" });
      mutateApiKeys();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create API key.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteApiKey = async (keyId: string, keyName: string) => {
    if (!window.confirm(`Revoke API key "${keyName}"? This cannot be undone.`))
      return;
    setActionError(null);
    try {
      await api.delete(`/api-keys/${keyId}`);
      mutateApiKeys(
        (current: typeof apiKeysEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as ApiKey[]).filter((k) => k.id !== keyId),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to revoke API key.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleCopyApiKey = async (key: string) => {
    await navigator.clipboard.writeText(key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const toggleApiKeyScope = (scope: string) => {
    setApiKeyForm((prev) => ({
      ...prev,
      scopes: prev.scopes.includes(scope)
        ? prev.scopes.filter((s) => s !== scope)
        : [...prev.scopes, scope],
    }));
  };

  return (
    <>
      {/* Action buttons */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowApiKeyModal(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus size={16} />
          Create API Key
        </button>
      </div>

      {/* Error state for initial load */}
      {error && <ErrorState message={error} onRetry={() => mutateApiKeys()} />}

      {/* Action error banner */}
      {actionError && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {actionError}
        </div>
      )}

      {!error && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              API Keys
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Manage API keys for CI/CD and programmatic access
            </p>
          </div>

          {apiKeysLoading ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {apiKeys.map((ak) => (
                <div
                  key={ak.id}
                  className="flex items-center justify-between px-6 py-4"
                >
                  <div className="flex items-center gap-4">
                    <Key
                      size={16}
                      className="text-gray-400 dark:text-gray-500"
                    />
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {ak.name}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                        <span className="font-mono text-xs">
                          {ak.key_prefix}...
                        </span>
                        {ak.scopes.map((scope) => (
                          <span
                            key={scope}
                            className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                          >
                            {scope}
                          </span>
                        ))}
                        <span className="text-xs">
                          Created:{" "}
                          {new Date(ak.created_at).toLocaleDateString()}
                        </span>
                        {ak.last_used_at && (
                          <span className="text-xs">
                            Last used:{" "}
                            {new Date(ak.last_used_at).toLocaleString()}
                          </span>
                        )}
                        {ak.expires_at && (
                          <span
                            className={`text-xs ${
                              new Date(ak.expires_at) < new Date()
                                ? "text-red-600 dark:text-red-400"
                                : "text-gray-500 dark:text-gray-400"
                            }`}
                          >
                            {new Date(ak.expires_at) < new Date()
                              ? "Expired"
                              : `Expires: ${new Date(ak.expires_at).toLocaleDateString()}`}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleDeleteApiKey(ak.id, ak.name)}
                      className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                      title="Revoke API key"
                    >
                      <Trash2 size={14} />
                      Revoke
                    </button>
                  </div>
                </div>
              ))}
              {apiKeys.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                  <Key size={20} className="mb-2" />
                  <p className="text-sm">No API keys created.</p>
                  <p className="mt-1 text-sm">
                    Create an API key for CI/CD integrations.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Create API Key Modal */}
      {showApiKeyModal && !createdApiKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Create API Key
              </h2>
              <button
                onClick={() => {
                  setShowApiKeyModal(false);
                  setApiKeyForm({
                    name: "",
                    scopes: ["read"],
                    expires_in_days: "",
                  });
                  setFormError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateApiKey} className="space-y-4">
              <div>
                <label
                  htmlFor="ak_name"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Name
                </label>
                <input
                  id="ak_name"
                  type="text"
                  required
                  maxLength={100}
                  value={apiKeyForm.name}
                  onChange={(e) =>
                    setApiKeyForm((p) => ({ ...p, name: e.target.value }))
                  }
                  placeholder="CI/CD Pipeline Key"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Scopes
                </label>
                <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
                  Select the permissions for this key
                </p>
                <div className="space-y-2">
                  {ALLOWED_SCOPES.map((scope) => (
                    <label
                      key={scope}
                      className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <input
                        type="checkbox"
                        checked={apiKeyForm.scopes.includes(scope)}
                        onChange={() => toggleApiKeyScope(scope)}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-medium">{scope}</span>
                      <span className="text-xs text-gray-400">
                        {scope === "read" &&
                          "- Read assets, findings, controls"}
                        {scope === "write" && "- Create and modify resources"}
                        {scope === "scan" && "- Trigger scans"}
                      </span>
                    </label>
                  ))}
                </div>
                {apiKeyForm.scopes.length === 0 && (
                  <p className="mt-1 text-xs text-red-500">
                    Select at least one scope.
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="ak_expiry"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Expiration (optional)
                </label>
                <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
                  Leave empty for a non-expiring key
                </p>
                <select
                  id="ak_expiry"
                  value={apiKeyForm.expires_in_days}
                  onChange={(e) =>
                    setApiKeyForm((p) => ({
                      ...p,
                      expires_in_days: e.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="">No expiration</option>
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                  <option value="180">180 days</option>
                  <option value="365">1 year</option>
                </select>
              </div>

              {formError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {formError}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowApiKeyModal(false);
                    setApiKeyForm({
                      name: "",
                      scopes: ["read"],
                      expires_in_days: "",
                    });
                    setFormError(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || apiKeyForm.scopes.length === 0}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Create Key"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* API Key Created -- show full key once */}
      {createdApiKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                API Key Created
              </h2>
            </div>

            <div className="mb-4 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 dark:border-yellow-600 dark:bg-yellow-900/20">
              <p className="text-sm font-medium text-yellow-800 dark:text-yellow-300">
                Copy your API key now. It will not be shown again.
              </p>
            </div>

            <div className="mb-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Name
              </label>
              <p className="text-sm text-gray-900 dark:text-gray-100">
                {createdApiKey.name}
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                API Key
              </label>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 break-all rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 font-mono text-sm dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100">
                  {createdApiKey.api_key}
                </code>
                <button
                  onClick={() => handleCopyApiKey(createdApiKey.api_key)}
                  className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  title="Copy to clipboard"
                >
                  <Copy size={14} />
                  {copiedKey ? "Copied" : "Copy"}
                </button>
              </div>
            </div>

            <div className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              <p>
                Use this key in the <code>Authorization</code> header:
              </p>
              <code className="mt-1 block rounded-lg bg-gray-100 px-3 py-2 text-xs dark:bg-gray-900 dark:text-gray-300">
                Authorization: Bearer {createdApiKey.key_prefix}...
              </code>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => {
                  setCreatedApiKey(null);
                  setShowApiKeyModal(false);
                }}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
