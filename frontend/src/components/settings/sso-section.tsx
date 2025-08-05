"use client";

import { useCallback, useState } from "react";
import {
  AlertTriangle,
  Check,
  ExternalLink,
  Globe,
  Loader2,
  Shield,
  Trash2,
} from "lucide-react";
import useSWR from "swr";
import api from "@/lib/api";
import type { SsoConfig, SsoProvider, SsoTestResult } from "@/types";

const SSO_PROVIDERS: { value: SsoProvider; label: string }[] = [
  { value: "azure_ad", label: "Azure AD (Entra ID)" },
  { value: "okta", label: "Okta" },
  { value: "google", label: "Google Workspace" },
  { value: "custom_oidc", label: "Custom OIDC" },
];

const PROVIDER_TEMPLATES: Record<
  SsoProvider,
  { issuer_url: string; help: string }
> = {
  azure_ad: {
    issuer_url: "https://login.microsoftonline.com/{tenant_id}/v2.0",
    help: "Replace {tenant_id} with your Azure AD (Entra ID) tenant ID",
  },
  okta: {
    issuer_url: "https://{domain}.okta.com",
    help: "Replace {domain} with your Okta domain",
  },
  google: {
    issuer_url: "https://accounts.google.com",
    help: "Use this URL as-is for Google Workspace",
  },
  custom_oidc: {
    issuer_url: "",
    help: "Enter the OIDC issuer URL for your identity provider",
  },
};

interface SsoFormState {
  provider: SsoProvider;
  client_id: string;
  client_secret: string;
  issuer_url: string;
  metadata_url: string;
  domain_restriction: string;
  auto_provision: boolean;
  default_role: string;
}

const EMPTY_FORM: SsoFormState = {
  provider: "azure_ad",
  client_id: "",
  client_secret: "",
  issuer_url: PROVIDER_TEMPLATES.azure_ad.issuer_url,
  metadata_url: "",
  domain_restriction: "",
  auto_provision: true,
  default_role: "viewer",
};

export default function SsoSection() {
  const {
    data: ssoEnvelope,
    error: ssoError,
    isLoading: ssoLoading,
    mutate: mutateSso,
  } = useSWR("/sso/config");

  const ssoConfig = ssoEnvelope?.data as SsoConfig | null | undefined;

  const [form, setForm] = useState<SsoFormState>(EMPTY_FORM);
  const [formInitialized, setFormInitialized] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<SsoTestResult | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [toggling, setToggling] = useState(false);

  // Initialize form from existing config
  if (!formInitialized && ssoConfig && !ssoLoading) {
    setForm({
      provider: ssoConfig.provider,
      client_id: ssoConfig.client_id,
      client_secret: "",
      issuer_url: ssoConfig.issuer_url,
      metadata_url: ssoConfig.metadata_url ?? "",
      domain_restriction: ssoConfig.domain_restriction ?? "",
      auto_provision: ssoConfig.auto_provision,
      default_role: ssoConfig.default_role,
    });
    setFormInitialized(true);
  }

  // When no config exists and data has loaded, mark as initialized
  if (
    !formInitialized &&
    !ssoConfig &&
    !ssoLoading &&
    ssoEnvelope !== undefined
  ) {
    setFormInitialized(true);
  }

  const handleProviderChange = useCallback(
    (provider: SsoProvider) => {
      const template = PROVIDER_TEMPLATES[provider];
      setForm((prev) => ({
        ...prev,
        provider,
        issuer_url: ssoConfig ? prev.issuer_url : template.issuer_url,
      }));
    },
    [ssoConfig],
  );

  const handleSave = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSaving(true);
      setSaveError(null);
      setSaveSuccess(false);

      try {
        const payload: Record<string, unknown> = {
          provider: form.provider,
          client_id: form.client_id,
          client_secret: form.client_secret,
          issuer_url: form.issuer_url,
          metadata_url: form.metadata_url || null,
          domain_restriction: form.domain_restriction || null,
          auto_provision: form.auto_provision,
          default_role: form.default_role,
        };

        await api.put("/sso/config", payload);
        await mutateSso();
        setSaveSuccess(true);
        // Clear the secret field after save
        setForm((prev) => ({ ...prev, client_secret: "" }));
        setTimeout(() => setSaveSuccess(false), 3000);
      } catch (err: unknown) {
        const axiosErr = err as {
          response?: { data?: { error?: string; detail?: string } };
        };
        setSaveError(
          axiosErr.response?.data?.error ??
            axiosErr.response?.data?.detail ??
            "Failed to save SSO configuration.",
        );
        setTimeout(() => setSaveError(null), 5000);
      } finally {
        setSaving(false);
      }
    },
    [form, mutateSso],
  );

  const handleTest = useCallback(async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post("/sso/test");
      setTestResult(res.data.data as SsoTestResult);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { error?: string; detail?: string } };
      };
      setTestResult({
        success: false,
        issuer: null,
        authorization_endpoint: null,
        token_endpoint: null,
        error:
          axiosErr.response?.data?.error ??
          axiosErr.response?.data?.detail ??
          "Test request failed.",
      });
    } finally {
      setTesting(false);
    }
  }, []);

  const handleToggleActive = useCallback(async () => {
    if (!ssoConfig) return;
    setToggling(true);
    try {
      await api.patch("/sso/config", { is_active: !ssoConfig.is_active });
      await mutateSso();
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string } };
      };
      setSaveError(axiosErr.response?.data?.detail ?? "Failed to toggle SSO.");
      setTimeout(() => setSaveError(null), 5000);
    } finally {
      setToggling(false);
    }
  }, [ssoConfig, mutateSso]);

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    try {
      await api.delete("/sso/config");
      await mutateSso();
      setForm(EMPTY_FORM);
      setFormInitialized(false);
      setShowDeleteConfirm(false);
      setTestResult(null);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string } };
      };
      setSaveError(
        axiosErr.response?.data?.detail ??
          "Failed to delete SSO configuration.",
      );
      setTimeout(() => setSaveError(null), 5000);
    } finally {
      setDeleting(false);
    }
  }, [mutateSso]);

  const currentTemplate = PROVIDER_TEMPLATES[form.provider];
  const isFormValid =
    form.client_id.trim().length > 0 &&
    form.issuer_url.trim().length > 0 &&
    // Require client_secret only when creating (no existing config)
    (ssoConfig ? true : form.client_secret.trim().length > 0);

  if (ssoLoading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Globe size={20} className="text-indigo-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Single Sign-On (SSO)
            </h2>
          </div>
        </div>
        <div className="flex h-48 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe size={20} className="text-indigo-500" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Single Sign-On (SSO)
              </h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Connect an identity provider for enterprise authentication
              </p>
            </div>
          </div>
          {ssoConfig && (
            <div className="flex items-center gap-3">
              {ssoConfig.is_active ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                  <Check size={14} /> Active
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-yellow-50 px-3 py-1 text-xs font-medium text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
                  <AlertTriangle size={14} /> Inactive
                </span>
              )}
              <button
                onClick={handleToggleActive}
                disabled={toggling}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  ssoConfig.is_active
                    ? "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                    : "bg-green-600 text-white hover:bg-green-700"
                }`}
              >
                {toggling ? "..." : ssoConfig.is_active ? "Disable" : "Enable"}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="px-6 py-5">
        {ssoError && (
          <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
            Failed to load SSO configuration.
          </div>
        )}

        {saveError && (
          <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
            {saveError}
          </div>
        )}

        {saveSuccess && (
          <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
            SSO configuration saved successfully.
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-5">
          {/* Provider selector */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Identity Provider
            </label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {SSO_PROVIDERS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => handleProviderChange(p.value)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    form.provider === p.value
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-300"
                      : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Client ID */}
          <div>
            <label
              htmlFor="sso-client-id"
              className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Client ID
            </label>
            <input
              id="sso-client-id"
              type="text"
              value={form.client_id}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, client_id: e.target.value }))
              }
              placeholder="Application (client) ID from your IdP"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>

          {/* Client Secret */}
          <div>
            <label
              htmlFor="sso-client-secret"
              className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Client Secret
              {ssoConfig && (
                <span className="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">
                  (leave blank to keep existing)
                </span>
              )}
            </label>
            <input
              id="sso-client-secret"
              type="password"
              value={form.client_secret}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  client_secret: e.target.value,
                }))
              }
              placeholder={
                ssoConfig ? "Enter new secret to update" : "Client secret"
              }
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>

          {/* Issuer URL */}
          <div>
            <label
              htmlFor="sso-issuer-url"
              className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Issuer URL
            </label>
            <input
              id="sso-issuer-url"
              type="url"
              value={form.issuer_url}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, issuer_url: e.target.value }))
              }
              placeholder="https://..."
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {currentTemplate.help}
            </p>
          </div>

          {/* Metadata URL (optional) */}
          <div>
            <label
              htmlFor="sso-metadata-url"
              className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Discovery / Metadata URL{" "}
              <span className="font-normal text-gray-500">(optional)</span>
            </label>
            <input
              id="sso-metadata-url"
              type="url"
              value={form.metadata_url}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  metadata_url: e.target.value,
                }))
              }
              placeholder="https://.../.well-known/openid-configuration"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Override the OIDC discovery URL if it differs from the standard
              path.
            </p>
          </div>

          {/* Domain restriction */}
          <div>
            <label
              htmlFor="sso-domain"
              className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Domain Restriction{" "}
              <span className="font-normal text-gray-500">(optional)</span>
            </label>
            <input
              id="sso-domain"
              type="text"
              value={form.domain_restriction}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  domain_restriction: e.target.value,
                }))
              }
              placeholder="company.com"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Only allow users with email addresses from this domain to log in
              via SSO.
            </p>
          </div>

          {/* Auto-provision toggle */}
          <div className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3 dark:border-gray-700">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                Auto-provision users
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Automatically create user accounts on first SSO login
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={form.auto_provision}
              onClick={() =>
                setForm((prev) => ({
                  ...prev,
                  auto_provision: !prev.auto_provision,
                }))
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ${
                form.auto_provision
                  ? "bg-indigo-600"
                  : "bg-gray-200 dark:bg-gray-600"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 translate-y-0.5 transform rounded-full bg-white shadow ring-0 transition-transform duration-200 ${
                  form.auto_provision ? "translate-x-[22px]" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>

          {/* Default role */}
          <div>
            <label
              htmlFor="sso-default-role"
              className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Default Role for New Users
            </label>
            <select
              id="sso-default-role"
              value={form.default_role}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  default_role: e.target.value,
                }))
              }
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            >
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
            </select>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Role assigned to auto-provisioned users on their first SSO login.
            </p>
          </div>

          {/* Test connection result */}
          {testResult && (
            <div
              className={`rounded-lg px-4 py-3 text-sm ${
                testResult.success
                  ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"
                  : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
              }`}
            >
              {testResult.success ? (
                <div className="space-y-1">
                  <p className="font-medium">OIDC discovery successful</p>
                  {testResult.issuer && (
                    <p className="text-xs">Issuer: {testResult.issuer}</p>
                  )}
                  {testResult.authorization_endpoint && (
                    <p className="flex items-center gap-1 text-xs">
                      <ExternalLink size={12} />
                      Auth endpoint: {testResult.authorization_endpoint}
                    </p>
                  )}
                  {testResult.token_endpoint && (
                    <p className="flex items-center gap-1 text-xs">
                      <ExternalLink size={12} />
                      Token endpoint: {testResult.token_endpoint}
                    </p>
                  )}
                </div>
              ) : (
                <p>{testResult.error ?? "Connection test failed."}</p>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center justify-between border-t border-gray-200 pt-4 dark:border-gray-700">
            <div className="flex items-center gap-2">
              {ssoConfig && (
                <>
                  <button
                    type="button"
                    onClick={handleTest}
                    disabled={testing}
                    className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    {testing ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Shield size={16} />
                    )}
                    Test Connection
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                    className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
                    title="Delete SSO configuration"
                  >
                    <Trash2 size={16} />
                  </button>
                </>
              )}
            </div>
            <button
              type="submit"
              disabled={saving || !isFormValid}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving
                ? "Saving..."
                : ssoConfig
                  ? "Update Configuration"
                  : "Save Configuration"}
            </button>
          </div>
        </form>

        {/* Delete confirmation */}
        {showDeleteConfirm && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-900/20">
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              Are you sure you want to delete the SSO configuration?
            </p>
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              This will disable SSO login for all users in this tenant. Users
              will need to sign in with email and password.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Yes, Delete"}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
