"use client";

import { useCallback, useState } from "react";
import {
  Check,
  Copy,
  Key,
  Loader2,
  RefreshCw,
  Trash2,
  Users,
} from "lucide-react";
import useSWR from "swr";
import api from "@/lib/api";
import type { ApiKey } from "@/types";

export default function ScimSection() {
  const { data: apiKeysEnvelope, mutate: mutateApiKeys } = useSWR("/api-keys");

  const apiKeys = (apiKeysEnvelope?.data ?? []) as ApiKey[];
  const scimKey = apiKeys.find((k) => k.scopes.includes("scim") && k.is_active);

  const [generating, setGenerating] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  const scimEndpointUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/scim/v2/`
      : "/scim/v2/";

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    setNewToken(null);
    try {
      const res = await api.post("/api-keys", {
        name: "SCIM Provisioning",
        scopes: ["scim"],
      });
      const created = res.data.data as { api_key: string };
      setNewToken(created.api_key);
      mutateApiKeys();
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string; error?: string } };
      };
      setError(
        axiosErr.response?.data?.detail ??
          axiosErr.response?.data?.error ??
          "Failed to generate SCIM token.",
      );
      setTimeout(() => setError(null), 5000);
    } finally {
      setGenerating(false);
    }
  }, [mutateApiKeys]);

  const handleRevoke = useCallback(async () => {
    if (!scimKey) return;
    if (
      !window.confirm(
        "Revoke the SCIM token? This will immediately stop all IdP provisioning.",
      )
    )
      return;

    setRevoking(true);
    setError(null);
    setNewToken(null);
    try {
      await api.delete(`/api-keys/${scimKey.id}`);
      mutateApiKeys();
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string; error?: string } };
      };
      setError(
        axiosErr.response?.data?.detail ??
          axiosErr.response?.data?.error ??
          "Failed to revoke SCIM token.",
      );
      setTimeout(() => setError(null), 5000);
    } finally {
      setRevoking(false);
    }
  }, [scimKey, mutateApiKeys]);

  const handleCopyUrl = useCallback(async () => {
    await navigator.clipboard.writeText(scimEndpointUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  }, [scimEndpointUrl]);

  const handleCopyToken = useCallback(async () => {
    if (!newToken) return;
    await navigator.clipboard.writeText(newToken);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2000);
  }, [newToken]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Users size={20} className="text-blue-600 dark:text-blue-400" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            SCIM Provisioning
          </h2>
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Configure your Identity Provider (Azure AD, Okta, etc.) with the
          endpoint URL and bearer token below to enable automatic user
          provisioning.
        </p>
      </div>

      <div className="space-y-4 px-6 py-4">
        {error && (
          <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Status */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Status:
          </span>
          {scimKey ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
              <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
              Active
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-400">
              <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
              Inactive
            </span>
          )}
        </div>

        {/* SCIM Endpoint URL */}
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
            SCIM Endpoint URL
          </label>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm font-mono text-gray-800 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200">
              {scimEndpointUrl}
            </code>
            <button
              onClick={handleCopyUrl}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              title="Copy endpoint URL"
            >
              {copiedUrl ? <Check size={14} /> : <Copy size={14} />}
              {copiedUrl ? "Copied" : "Copy"}
            </button>
          </div>
        </div>

        {/* SCIM Token */}
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
            SCIM Bearer Token
          </label>
          {scimKey ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="flex flex-1 items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-600 dark:bg-gray-700">
                  <Key size={14} className="text-gray-400 dark:text-gray-500" />
                  <span className="font-mono text-sm text-gray-800 dark:text-gray-200">
                    {scimKey.key_prefix}...
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    (created {new Date(scimKey.created_at).toLocaleDateString()}
                    )
                  </span>
                </div>
                <button
                  onClick={handleRevoke}
                  disabled={revoking}
                  className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:bg-gray-800 dark:text-red-400 dark:hover:bg-red-900/20"
                >
                  {revoking ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Trash2 size={14} />
                  )}
                  Revoke
                </button>
              </div>

              {/* Show newly created token */}
              {newToken && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
                  <p className="mb-2 text-xs font-medium text-amber-800 dark:text-amber-300">
                    Copy your SCIM token now. It will not be shown again.
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 break-all rounded bg-white px-2 py-1 font-mono text-xs text-gray-800 dark:bg-gray-800 dark:text-gray-200">
                      {newToken}
                    </code>
                    <button
                      onClick={handleCopyToken}
                      className="flex shrink-0 items-center gap-1 rounded border border-amber-300 bg-white px-2 py-1 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-50 dark:border-amber-700 dark:bg-gray-800 dark:text-amber-400 dark:hover:bg-amber-900/30"
                    >
                      {copiedToken ? <Check size={12} /> : <Copy size={12} />}
                      {copiedToken ? "Copied" : "Copy"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No SCIM token configured. Generate one to enable IdP
                provisioning.
              </p>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {generating ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <RefreshCw size={16} />
                )}
                Generate SCIM Token
              </button>
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-900/20">
          <h3 className="text-sm font-medium text-blue-800 dark:text-blue-300">
            Setup Instructions
          </h3>
          <ol className="mt-2 list-inside list-decimal space-y-1 text-sm text-blue-700 dark:text-blue-400">
            <li>Copy the SCIM Endpoint URL above</li>
            <li>Generate a SCIM Bearer Token (if not already created)</li>
            <li>
              In your IdP (Azure AD, Okta, etc.), configure SCIM provisioning
              with:
              <ul className="ml-5 mt-1 list-disc space-y-0.5">
                <li>
                  <strong>Tenant URL:</strong> the SCIM Endpoint URL
                </li>
                <li>
                  <strong>Secret Token:</strong> the SCIM Bearer Token
                </li>
              </ul>
            </li>
            <li>
              Enable provisioning and map user attributes (userName, name,
              active)
            </li>
            <li>Test the connection from your IdP</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
