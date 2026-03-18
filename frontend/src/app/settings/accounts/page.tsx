"use client";

import { useState } from "react";
import useSWR from "swr";
import { Calendar, Plus, RefreshCw, Trash2, X } from "lucide-react";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type { CloudAccount, CloudProvider } from "@/types";

interface AddAccountForm {
  provider: CloudProvider;
  display_name: string;
  provider_account_id: string;
  tenant_id: string;
  client_id: string;
  client_secret: string;
  access_key_id: string;
  secret_access_key: string;
  region: string;
  role_arn: string;
}

const EMPTY_FORM: AddAccountForm = {
  provider: "azure",
  display_name: "",
  provider_account_id: "",
  tenant_id: "",
  client_id: "",
  client_secret: "",
  access_key_id: "",
  secret_access_key: "",
  region: "us-east-1",
  role_arn: "",
};

const SCHEDULE_PRESETS: { label: string; value: string }[] = [
  { label: "Disabled", value: "" },
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily (midnight)", value: "0 0 * * *" },
  { label: "Weekly (Sunday)", value: "0 0 * * 0" },
];

export default function AccountsPage() {
  const {
    data: accountsEnvelope,
    error: accountsError,
    isLoading: accountsLoading,
    mutate: mutateAccounts,
  } = useSWR("/accounts");

  const accounts = (accountsEnvelope?.data ?? []) as CloudAccount[];
  const error = accountsError?.message ?? accountsEnvelope?.error ?? null;

  const [actionError, setActionError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [form, setForm] = useState<AddAccountForm>(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Test connection state for Add Account modal
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [testConnectionResult, setTestConnectionResult] = useState<{
    success: boolean;
    resource_count: number;
    message: string;
  } | null>(null);

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setTestConnectionResult(null);
    try {
      const payload =
        form.provider === "azure"
          ? {
              provider: form.provider,
              tenant_id: form.tenant_id,
              client_id: form.client_id,
              client_secret: form.client_secret,
              subscription_id: form.provider_account_id,
            }
          : {
              provider: form.provider,
              access_key_id: form.access_key_id,
              secret_access_key: form.secret_access_key,
              region: form.region || "us-east-1",
              role_arn: form.role_arn || undefined,
            };
      const res = await api.post("/accounts/test-connection", payload);
      setTestConnectionResult(
        res.data.data as {
          success: boolean;
          resource_count: number;
          message: string;
        },
      );
    } catch {
      setTestConnectionResult({
        success: false,
        resource_count: 0,
        message: "Request failed. Please check your network connection.",
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const isTestConnectionReady =
    form.provider === "azure"
      ? form.provider_account_id.trim().length > 0 &&
        form.tenant_id.trim().length > 0 &&
        form.client_id.trim().length > 0 &&
        form.client_secret.trim().length > 0
      : form.access_key_id.trim().length > 0 &&
        form.secret_access_key.trim().length > 0;

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);

    try {
      const credentials =
        form.provider === "azure"
          ? {
              tenant_id: form.tenant_id,
              client_id: form.client_id,
              client_secret: form.client_secret,
            }
          : {
              access_key_id: form.access_key_id,
              secret_access_key: form.secret_access_key,
              region: form.region || "us-east-1",
              ...(form.role_arn ? { role_arn: form.role_arn } : {}),
            };
      await api.post("/accounts", {
        provider: form.provider,
        display_name: form.display_name,
        provider_account_id: form.provider_account_id,
        credentials,
      });
      setShowAddModal(false);
      setForm(EMPTY_FORM);
      setTestConnectionResult(null);
      mutateAccounts();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      setFormError(
        axiosErr.response?.data?.error ??
          "Failed to add account. Check your credentials.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const [scanningId, setScanningId] = useState<string | null>(null);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const handleTriggerScan = async (accountId: string) => {
    setScanningId(accountId);
    setScanMessage(null);
    try {
      await api.post("/scans", { cloud_account_id: accountId });
      setScanMessage("Scan started successfully!");
      setTimeout(() => setScanMessage(null), 5000);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { status?: number; data?: { detail?: string } };
      };
      if (axiosErr.response?.status === 429) {
        setScanMessage("Rate limit reached — try again later.");
      } else if (axiosErr.response?.status === 409) {
        setScanMessage("A scan is already running.");
      } else {
        setScanMessage(axiosErr.response?.data?.detail ?? "Scan failed.");
      }
      setTimeout(() => setScanMessage(null), 5000);
    } finally {
      setScanningId(null);
    }
  };

  const handleDeleteAccount = async (accountId: string, name: string) => {
    if (!window.confirm(`Remove "${name}"? Associated data will be deleted.`)) {
      return;
    }
    setActionError(null);
    try {
      await api.delete(`/accounts/${accountId}`);
      mutateAccounts(
        (current: typeof accountsEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as CloudAccount[]).filter(
              (a) => a.id !== accountId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      setActionError(
        axiosErr.response?.data?.error ?? "Failed to remove account.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const isActive = (account: CloudAccount) => account.status === "active";

  const updateField = (field: keyof AddAccountForm, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <>
      {/* Action buttons */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus size={16} />
          Add Account
        </button>
      </div>

      {/* Error state for initial load */}
      {error && <ErrorState message={error} onRetry={() => mutateAccounts()} />}

      {/* Action error banner */}
      {actionError && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {actionError}
        </div>
      )}

      {!error && (
        <>
          {/* Cloud Accounts */}
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Cloud Accounts
              </h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Connected cloud provider subscriptions and accounts
              </p>
            </div>

            {accountsLoading ? (
              <div className="flex h-48 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
              </div>
            ) : (
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {accounts.map((account) => (
                  <div
                    key={account.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={`h-3 w-3 rounded-full ${
                          isActive(account) ? "bg-green-400" : "bg-gray-300"
                        }`}
                        title={account.status}
                      />
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {account.display_name}
                        </p>
                        <div className="mt-1 flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
                          <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                            {account.provider.toUpperCase()}
                          </span>
                          <span className="font-mono text-xs">
                            {account.provider_account_id}
                          </span>
                          {account.last_scan_at && (
                            <span>
                              Last scan:{" "}
                              {new Date(account.last_scan_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {scanMessage && scanningId === null && (
                        <span className="text-xs text-gray-600 dark:text-gray-300">
                          {scanMessage}
                        </span>
                      )}
                      <button
                        onClick={() => handleTriggerScan(account.id)}
                        disabled={
                          !isActive(account) || scanningId === account.id
                        }
                        className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                        title="Trigger scan"
                      >
                        <RefreshCw
                          size={14}
                          className={
                            scanningId === account.id ? "animate-spin" : ""
                          }
                        />
                        {scanningId === account.id ? "Scanning..." : "Scan"}
                      </button>
                      <button
                        onClick={() =>
                          handleDeleteAccount(account.id, account.display_name)
                        }
                        className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                        title="Remove account"
                      >
                        <Trash2 size={14} />
                        Remove
                      </button>
                    </div>
                  </div>
                ))}

                {accounts.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <p className="text-sm">No cloud accounts connected yet.</p>
                    <p className="mt-1 text-sm">
                      Click &quot;Add Account&quot; to get started.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Scan Configuration */}
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Scan Configuration
              </h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Configure automatic scan schedules for each account
              </p>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {accounts.map((account) => (
                <ScanScheduleRow
                  key={account.id}
                  account={account}
                  onUpdated={() => mutateAccounts()}
                />
              ))}
              {accounts.length === 0 && (
                <div className="flex items-center justify-center py-8 text-sm text-gray-500 dark:text-gray-400">
                  Add a cloud account to configure scan schedules.
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Add Account Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Add Cloud Account
              </h2>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setForm(EMPTY_FORM);
                  setFormError(null);
                  setTestConnectionResult(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleAddAccount} className="space-y-4">
              {/* Provider */}
              <div>
                <label
                  htmlFor="provider"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Cloud Provider
                </label>
                <select
                  id="provider"
                  value={form.provider}
                  onChange={(e) => updateField("provider", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="azure">Azure</option>
                  <option value="aws">AWS</option>
                </select>
              </div>

              {/* Display Name */}
              <div>
                <label
                  htmlFor="display_name"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Display Name
                </label>
                <input
                  id="display_name"
                  type="text"
                  required
                  value={form.display_name}
                  onChange={(e) => updateField("display_name", e.target.value)}
                  placeholder="Production Subscription"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              {/* Subscription / Account ID */}
              <div>
                <label
                  htmlFor="provider_account_id"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  {form.provider === "azure"
                    ? "Subscription ID"
                    : "AWS Account ID"}
                </label>
                <input
                  id="provider_account_id"
                  type="text"
                  required
                  value={form.provider_account_id}
                  onChange={(e) =>
                    updateField("provider_account_id", e.target.value)
                  }
                  placeholder={
                    form.provider === "azure"
                      ? "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                      : "123456789012"
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              {/* Credentials section */}
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-600 dark:bg-gray-900/50">
                <h3 className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
                  {form.provider === "azure"
                    ? "Azure Service Principal"
                    : "AWS Credentials"}
                </h3>

                {form.provider === "azure" ? (
                  <>
                    <div className="mb-3">
                      <label
                        htmlFor="azure_tenant_id"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Azure Tenant ID
                      </label>
                      <input
                        id="azure_tenant_id"
                        type="text"
                        required
                        value={form.tenant_id}
                        onChange={(e) =>
                          updateField("tenant_id", e.target.value)
                        }
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                    <div className="mb-3">
                      <label
                        htmlFor="azure_client_id"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Client ID (App ID)
                      </label>
                      <input
                        id="azure_client_id"
                        type="text"
                        required
                        value={form.client_id}
                        onChange={(e) =>
                          updateField("client_id", e.target.value)
                        }
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="azure_client_secret"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Client Secret
                      </label>
                      <input
                        id="azure_client_secret"
                        type="password"
                        required
                        value={form.client_secret}
                        onChange={(e) =>
                          updateField("client_secret", e.target.value)
                        }
                        placeholder="••••••••••••"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="mb-3">
                      <label
                        htmlFor="aws_access_key_id"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Access Key ID
                      </label>
                      <input
                        id="aws_access_key_id"
                        type="text"
                        required
                        value={form.access_key_id}
                        onChange={(e) =>
                          updateField("access_key_id", e.target.value)
                        }
                        placeholder="AKIAIOSFODNN7EXAMPLE"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                    <div className="mb-3">
                      <label
                        htmlFor="aws_secret_access_key"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Secret Access Key
                      </label>
                      <input
                        id="aws_secret_access_key"
                        type="password"
                        required
                        value={form.secret_access_key}
                        onChange={(e) =>
                          updateField("secret_access_key", e.target.value)
                        }
                        placeholder="••••••••••••"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                    <div className="mb-3">
                      <label
                        htmlFor="aws_region"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Region
                      </label>
                      <select
                        id="aws_region"
                        value={form.region}
                        onChange={(e) => updateField("region", e.target.value)}
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      >
                        <option value="us-east-1">US East (N. Virginia)</option>
                        <option value="us-east-2">US East (Ohio)</option>
                        <option value="us-west-1">
                          US West (N. California)
                        </option>
                        <option value="us-west-2">US West (Oregon)</option>
                        <option value="eu-west-1">EU (Ireland)</option>
                        <option value="eu-west-2">EU (London)</option>
                        <option value="eu-west-3">EU (Paris)</option>
                        <option value="eu-central-1">EU (Frankfurt)</option>
                        <option value="ap-southeast-1">
                          Asia Pacific (Singapore)
                        </option>
                        <option value="ap-southeast-2">
                          Asia Pacific (Sydney)
                        </option>
                        <option value="ap-northeast-1">
                          Asia Pacific (Tokyo)
                        </option>
                      </select>
                    </div>
                    <div>
                      <label
                        htmlFor="aws_role_arn"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Role ARN{" "}
                        <span className="text-gray-400">
                          (optional, for cross-account)
                        </span>
                      </label>
                      <input
                        id="aws_role_arn"
                        type="text"
                        value={form.role_arn}
                        onChange={(e) =>
                          updateField("role_arn", e.target.value)
                        }
                        placeholder="arn:aws:iam::123456789012:role/NimbusGuardRole"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                  </>
                )}
              </div>

              {/* Test Connection */}
              {(form.provider === "azure" || form.provider === "aws") && (
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={isTestingConnection || !isTestConnectionReady}
                    className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    {isTestingConnection ? (
                      <>
                        <RefreshCw size={14} className="animate-spin" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <RefreshCw size={14} />
                        Test Connection
                      </>
                    )}
                  </button>
                  {testConnectionResult && (
                    <div
                      className={`rounded-lg px-4 py-3 text-sm ${
                        testConnectionResult.success
                          ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"
                          : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
                      }`}
                    >
                      {testConnectionResult.message}
                    </div>
                  )}
                </div>
              )}

              {/* Error message */}
              {formError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {formError}
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false);
                    setForm(EMPTY_FORM);
                    setFormError(null);
                    setTestConnectionResult(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Adding..." : "Add Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

// -- Scan Schedule per-account row ----------------------------------------

function ScanScheduleRow({
  account,
  onUpdated,
}: {
  account: CloudAccount;
  onUpdated: () => void;
}) {
  const current = account.scan_schedule;
  const [schedule, setSchedule] = useState(current ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isDirty = schedule !== (current ?? "");

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await api.put(`/accounts/${account.id}/schedule`, {
        scan_schedule: schedule || null,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onUpdated();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setSaveError(
        axiosErr.response?.data?.detail ?? "Failed to save schedule.",
      );
      setTimeout(() => setSaveError(null), 5000);
    } finally {
      setSaving(false);
    }
  };

  const presetMatch = SCHEDULE_PRESETS.find((p) => p.value === schedule);

  return (
    <div className="flex items-center justify-between px-6 py-4">
      <div className="flex items-center gap-3">
        <Calendar size={16} className="text-gray-400 dark:text-gray-500" />
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {account.display_name}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {current ? `Schedule: ${current}` : "No schedule set"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <select
          value={presetMatch ? schedule : "__custom__"}
          onChange={(e) => {
            if (e.target.value !== "__custom__") {
              setSchedule(e.target.value);
            }
          }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
        >
          {SCHEDULE_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
          {!presetMatch && schedule && (
            <option value="__custom__">Custom: {schedule}</option>
          )}
        </select>
        {isDirty && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        )}
        {saved && (
          <span className="text-xs text-green-600 dark:text-green-400">
            Saved
          </span>
        )}
        {saveError && (
          <span className="text-xs text-red-600 dark:text-red-400">
            {saveError}
          </span>
        )}
      </div>
    </div>
  );
}
