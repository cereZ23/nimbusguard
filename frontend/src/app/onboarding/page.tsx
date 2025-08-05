"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Cloud,
  Shield,
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
  Rocket,
  Eye,
  EyeOff,
  LayoutDashboard,
} from "lucide-react";
import api from "@/lib/api";

// ── Step definitions ────────────────────────────────────────────────

type WizardStep =
  | "welcome"
  | "provider"
  | "credentials"
  | "test"
  | "confirm"
  | "success";

const STEPS: WizardStep[] = [
  "welcome",
  "provider",
  "credentials",
  "test",
  "confirm",
  "success",
];

const STEP_LABELS: Record<WizardStep, string> = {
  welcome: "Welcome",
  provider: "Provider",
  credentials: "Credentials",
  test: "Test",
  confirm: "Confirm",
  success: "Done",
};

// ── Form state ──────────────────────────────────────────────────────

interface CredentialForm {
  display_name: string;
  subscription_id: string;
  tenant_id: string;
  client_id: string;
  client_secret: string;
}

const EMPTY_FORM: CredentialForm = {
  display_name: "",
  subscription_id: "",
  tenant_id: "",
  client_id: "",
  client_secret: "",
};

// ── Test connection result ──────────────────────────────────────────

interface TestResult {
  success: boolean;
  resource_count: number;
  message: string;
}

// ── Main component ──────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<WizardStep>("welcome");
  const [provider, setProvider] = useState<"azure" | null>(null);
  const [form, setForm] = useState<CredentialForm>(EMPTY_FORM);
  const [showGuide, setShowGuide] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  // Test connection state
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // Account creation state
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createdAccountId, setCreatedAccountId] = useState<string | null>(null);

  // Scan state
  const [isScanning, setIsScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const currentIndex = STEPS.indexOf(currentStep);

  const goNext = useCallback(() => {
    const idx = STEPS.indexOf(currentStep);
    if (idx < STEPS.length - 1) {
      setCurrentStep(STEPS[idx + 1]);
    }
  }, [currentStep]);

  const goBack = useCallback(() => {
    const idx = STEPS.indexOf(currentStep);
    if (idx > 0) {
      setCurrentStep(STEPS[idx - 1]);
    }
  }, [currentStep]);

  const updateField = (field: keyof CredentialForm, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const isCredentialsValid =
    form.display_name.trim().length > 0 &&
    form.subscription_id.trim().length > 0 &&
    form.tenant_id.trim().length > 0 &&
    form.client_id.trim().length > 0 &&
    form.client_secret.trim().length > 0;

  // ── Test connection handler ─────────────────────────────────────

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await api.post("/accounts/test-connection", {
        provider: "azure",
        tenant_id: form.tenant_id,
        client_id: form.client_id,
        client_secret: form.client_secret,
        subscription_id: form.subscription_id,
      });
      const data = res.data.data as TestResult;
      setTestResult(data);
    } catch {
      setTestResult({
        success: false,
        resource_count: 0,
        message: "Request failed. Please check your network connection.",
      });
    } finally {
      setIsTesting(false);
    }
  };

  // ── Create account handler ──────────────────────────────────────

  const handleCreateAccount = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      const res = await api.post("/accounts", {
        provider: "azure",
        display_name: form.display_name,
        provider_account_id: form.subscription_id,
        credentials: {
          tenant_id: form.tenant_id,
          client_id: form.client_id,
          client_secret: form.client_secret,
        },
      });
      const account = res.data.data as { id: string };
      setCreatedAccountId(account.id);
      goNext();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      setCreateError(
        axiosErr.response?.data?.error ?? "Failed to create account.",
      );
    } finally {
      setIsCreating(false);
    }
  };

  // ── Start scan handler ──────────────────────────────────────────

  const handleStartScan = async () => {
    if (!createdAccountId) return;
    setIsScanning(true);
    setScanMessage(null);
    try {
      await api.post("/scans", { cloud_account_id: createdAccountId });
      setScanMessage("Scan started successfully! Redirecting to dashboard...");
      setTimeout(() => router.push("/dashboard"), 2000);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { status?: number; data?: { detail?: string } };
      };
      if (axiosErr.response?.status === 409) {
        setScanMessage("A scan is already running.");
      } else {
        setScanMessage(
          axiosErr.response?.data?.detail ?? "Failed to start scan.",
        );
      }
    } finally {
      setIsScanning(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4 dark:bg-gray-900">
      <div className="w-full max-w-2xl">
        {/* Progress indicator */}
        <div className="mb-8 flex items-center justify-center gap-2">
          {STEPS.map((step, idx) => (
            <div key={step} className="flex items-center gap-2">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                  idx < currentIndex
                    ? "bg-green-500 text-white"
                    : idx === currentIndex
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                }`}
              >
                {idx < currentIndex ? <CheckCircle size={16} /> : idx + 1}
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={`hidden h-0.5 w-6 sm:block ${
                    idx < currentIndex
                      ? "bg-green-500"
                      : "bg-gray-200 dark:bg-gray-700"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step label */}
        <p className="mb-4 text-center text-xs font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
          {STEP_LABELS[currentStep]}
        </p>

        {/* Card */}
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          {/* ── Step 1: Welcome ─────────────────────────────────── */}
          {currentStep === "welcome" && (
            <div className="text-center">
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 dark:bg-blue-900/30">
                <Shield
                  size={32}
                  className="text-blue-600 dark:text-blue-400"
                />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Welcome to CSPM
              </h1>
              <p className="mx-auto mt-3 max-w-md text-gray-500 dark:text-gray-400">
                Let&apos;s connect your first cloud account. This wizard will
                guide you through setting up Azure credentials so we can start
                assessing your security posture.
              </p>
              <p className="mt-4 text-sm text-gray-400 dark:text-gray-500">
                It takes about 2 minutes to complete.
              </p>
              <div className="mt-8 flex justify-center">
                <button
                  onClick={goNext}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
                >
                  Get Started
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 2: Provider Selection ──────────────────────── */}
          {currentStep === "provider" && (
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Select a Cloud Provider
              </h2>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Choose the cloud provider you want to connect.
              </p>

              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Azure */}
                <button
                  onClick={() => setProvider("azure")}
                  className={`flex flex-col items-center gap-3 rounded-xl border-2 p-6 transition-all ${
                    provider === "azure"
                      ? "border-blue-600 bg-blue-50 dark:border-blue-500 dark:bg-blue-900/20"
                      : "border-gray-200 bg-white hover:border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:hover:border-gray-500"
                  }`}
                >
                  <Cloud
                    size={32}
                    className={
                      provider === "azure"
                        ? "text-blue-600 dark:text-blue-400"
                        : "text-gray-400"
                    }
                  />
                  <span
                    className={`text-sm font-semibold ${
                      provider === "azure"
                        ? "text-blue-600 dark:text-blue-400"
                        : "text-gray-700 dark:text-gray-300"
                    }`}
                  >
                    Microsoft Azure
                  </span>
                </button>

                {/* AWS (Coming Soon) */}
                <div className="relative flex flex-col items-center gap-3 rounded-xl border-2 border-gray-200 bg-gray-50 p-6 opacity-60 dark:border-gray-700 dark:bg-gray-800/50">
                  <Cloud
                    size={32}
                    className="text-gray-300 dark:text-gray-600"
                  />
                  <span className="text-sm font-semibold text-gray-400 dark:text-gray-500">
                    Amazon Web Services
                  </span>
                  <span className="absolute right-3 top-3 rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-gray-500 dark:bg-gray-700 dark:text-gray-400">
                    Coming Soon
                  </span>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={goBack}
                  className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  onClick={goNext}
                  disabled={!provider}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 3: Credentials ─────────────────────────────── */}
          {currentStep === "credentials" && (
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Azure Service Principal
              </h2>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Enter the credentials for the Azure Service Principal that will
                be used to read your cloud resources.
              </p>

              <div className="mt-6 space-y-4">
                {/* Display Name */}
                <div>
                  <label
                    htmlFor="wiz_display_name"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Display Name
                  </label>
                  <input
                    id="wiz_display_name"
                    type="text"
                    value={form.display_name}
                    onChange={(e) =>
                      updateField("display_name", e.target.value)
                    }
                    placeholder="e.g. Production Subscription"
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  />
                </div>

                {/* Subscription ID */}
                <div>
                  <label
                    htmlFor="wiz_subscription_id"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Subscription ID
                  </label>
                  <input
                    id="wiz_subscription_id"
                    type="text"
                    value={form.subscription_id}
                    onChange={(e) =>
                      updateField("subscription_id", e.target.value)
                    }
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  />
                </div>

                {/* Tenant ID */}
                <div>
                  <label
                    htmlFor="wiz_tenant_id"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Azure Tenant ID
                  </label>
                  <input
                    id="wiz_tenant_id"
                    type="text"
                    value={form.tenant_id}
                    onChange={(e) => updateField("tenant_id", e.target.value)}
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  />
                </div>

                {/* Client ID */}
                <div>
                  <label
                    htmlFor="wiz_client_id"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Client ID (App ID)
                  </label>
                  <input
                    id="wiz_client_id"
                    type="text"
                    value={form.client_id}
                    onChange={(e) => updateField("client_id", e.target.value)}
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  />
                </div>

                {/* Client Secret */}
                <div>
                  <label
                    htmlFor="wiz_client_secret"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Client Secret
                  </label>
                  <div className="relative mt-1">
                    <input
                      id="wiz_client_secret"
                      type={showSecret ? "text" : "password"}
                      value={form.client_secret}
                      onChange={(e) =>
                        updateField("client_secret", e.target.value)
                      }
                      placeholder="Enter your client secret"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                    />
                    <button
                      type="button"
                      onClick={() => setShowSecret(!showSecret)}
                      className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                      aria-label={showSecret ? "Hide secret" : "Show secret"}
                    >
                      {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Collapsible guide */}
              <div className="mt-6 rounded-lg border border-gray-200 dark:border-gray-600">
                <button
                  onClick={() => setShowGuide(!showGuide)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700/50"
                >
                  <span>How to get these credentials</span>
                  {showGuide ? (
                    <ChevronUp size={16} className="text-gray-400" />
                  ) : (
                    <ChevronDown size={16} className="text-gray-400" />
                  )}
                </button>
                {showGuide && (
                  <div className="border-t border-gray-200 px-4 py-3 text-sm text-gray-600 dark:border-gray-600 dark:text-gray-400">
                    <ol className="list-inside list-decimal space-y-2">
                      <li>
                        Go to{" "}
                        <strong>
                          Azure Portal &gt; Microsoft Entra ID &gt; App
                          registrations
                        </strong>
                      </li>
                      <li>
                        Click <strong>New registration</strong>. Name it
                        &quot;CSPM Reader&quot; and register.
                      </li>
                      <li>
                        Copy the <strong>Application (client) ID</strong> and{" "}
                        <strong>Directory (tenant) ID</strong> from the overview
                        page.
                      </li>
                      <li>
                        Go to <strong>Certificates &amp; secrets</strong> &gt;{" "}
                        <strong>New client secret</strong>. Copy the secret
                        value.
                      </li>
                      <li>
                        Go to the <strong>Subscription</strong> you want to
                        monitor. Copy the <strong>Subscription ID</strong>.
                      </li>
                      <li>
                        In the subscription, go to{" "}
                        <strong>Access control (IAM)</strong> &gt;{" "}
                        <strong>Add role assignment</strong>. Assign{" "}
                        <strong>Reader</strong> and{" "}
                        <strong>Security Reader</strong> roles to the app.
                      </li>
                    </ol>
                  </div>
                )}
              </div>

              <div className="mt-6 flex items-center justify-between">
                <button
                  onClick={goBack}
                  className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  onClick={goNext}
                  disabled={!isCredentialsValid}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 4: Test Connection ─────────────────────────── */}
          {currentStep === "test" && (
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Test Connection
              </h2>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Verify that CSPM can connect to your Azure subscription before
                proceeding.
              </p>

              <div className="mt-6 flex flex-col items-center gap-4">
                <button
                  onClick={handleTestConnection}
                  disabled={isTesting}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-8 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isTesting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Testing...
                    </>
                  ) : (
                    <>
                      <Cloud size={16} />
                      Test Connection
                    </>
                  )}
                </button>

                {/* Result display */}
                {testResult && (
                  <div
                    className={`mt-2 w-full rounded-lg border px-4 py-3 ${
                      testResult.success
                        ? "border-green-200 bg-green-50 dark:border-green-700 dark:bg-green-900/20"
                        : "border-red-200 bg-red-50 dark:border-red-700 dark:bg-red-900/20"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {testResult.success ? (
                        <CheckCircle
                          size={20}
                          className="mt-0.5 shrink-0 text-green-600 dark:text-green-400"
                        />
                      ) : (
                        <AlertCircle
                          size={20}
                          className="mt-0.5 shrink-0 text-red-600 dark:text-red-400"
                        />
                      )}
                      <div>
                        <p
                          className={`text-sm font-medium ${
                            testResult.success
                              ? "text-green-800 dark:text-green-300"
                              : "text-red-800 dark:text-red-300"
                          }`}
                        >
                          {testResult.success
                            ? "Connection successful"
                            : "Connection failed"}
                        </p>
                        <p
                          className={`mt-1 text-sm ${
                            testResult.success
                              ? "text-green-700 dark:text-green-400"
                              : "text-red-700 dark:text-red-400"
                          }`}
                        >
                          {testResult.message}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={goBack}
                  className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  onClick={goNext}
                  disabled={!testResult?.success}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 5: Confirmation ────────────────────────────── */}
          {currentStep === "confirm" && (
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Confirm &amp; Connect
              </h2>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Review the details below and click &quot;Connect Account&quot;
                to finish setup.
              </p>

              <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-600 dark:bg-gray-900/50">
                <dl className="divide-y divide-gray-200 dark:divide-gray-600">
                  <SummaryRow label="Provider" value="Azure" />
                  <SummaryRow label="Display Name" value={form.display_name} />
                  <SummaryRow
                    label="Subscription ID"
                    value={form.subscription_id}
                    mono
                  />
                  <SummaryRow label="Tenant ID" value={form.tenant_id} mono />
                  <SummaryRow label="Client ID" value={form.client_id} mono />
                  <SummaryRow
                    label="Client Secret"
                    value="**********************"
                  />
                  {testResult && (
                    <SummaryRow
                      label="Resources Found"
                      value={String(testResult.resource_count)}
                    />
                  )}
                </dl>
              </div>

              {createError && (
                <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {createError}
                </div>
              )}

              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={goBack}
                  className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <button
                  onClick={handleCreateAccount}
                  disabled={isCreating}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isCreating ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <CheckCircle size={16} />
                      Connect Account
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* ── Step 6: Success ─────────────────────────────────── */}
          {currentStep === "success" && (
            <div className="text-center">
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-green-50 dark:bg-green-900/30">
                <CheckCircle
                  size={32}
                  className="text-green-600 dark:text-green-400"
                />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                Account Connected!
              </h2>
              <p className="mx-auto mt-3 max-w-md text-gray-500 dark:text-gray-400">
                Your Azure subscription has been successfully connected. Run
                your first security scan to discover resources and assess your
                security posture.
              </p>

              {scanMessage && (
                <div className="mx-auto mt-4 max-w-md rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-700 dark:bg-blue-900/20 dark:text-blue-400">
                  {scanMessage}
                </div>
              )}

              <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                <button
                  onClick={handleStartScan}
                  disabled={isScanning}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isScanning ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Starting Scan...
                    </>
                  ) : (
                    <>
                      <Rocket size={16} />
                      Start First Scan
                    </>
                  )}
                </button>
                <button
                  onClick={() => router.push("/dashboard")}
                  className="flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-6 py-3 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  <LayoutDashboard size={16} />
                  Go to Dashboard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Helper components ───────────────────────────────────────────────

function SummaryRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <dt className="text-sm font-medium text-gray-500 dark:text-gray-400">
        {label}
      </dt>
      <dd
        className={`text-sm text-gray-900 dark:text-white ${
          mono ? "font-mono" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
