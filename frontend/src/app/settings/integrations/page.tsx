"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  Check,
  Globe,
  Hash,
  MessageSquare,
  Plus,
  Send,
  Trash2,
} from "lucide-react";
import Button from "@/components/ui/button";
import ConfirmDialog from "@/components/ui/confirm-dialog";
import Modal from "@/components/ui/modal";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type {
  JiraIntegration,
  JiraTestResult,
  SlackIntegration,
  SlackTestResult,
  Webhook,
  WebhookTestResult,
} from "@/types";

const ALLOWED_EVENTS = [
  "scan.completed",
  "scan.failed",
  "finding.high",
  "finding.critical_change",
];
const SLACK_EVENTS = [
  "scan.completed",
  "scan.failed",
  "finding.high",
  "finding.critical_change",
];
const JIRA_ISSUE_TYPES = ["Bug", "Task", "Story", "Epic", "Sub-task"];

type IntegrationTab = "webhooks" | "slack" | "jira";

export default function IntegrationsPage() {
  const [activeTab, setActiveTab] = useState<IntegrationTab>("webhooks");

  // -- SWR: webhooks --
  const {
    data: webhooksEnvelope,
    error: webhooksError,
    isLoading: webhooksLoading,
    mutate: mutateWebhooks,
  } = useSWR("/webhooks");

  // -- SWR: slack integrations --
  const {
    data: slackEnvelope,
    error: slackError,
    isLoading: slackLoading,
    mutate: mutateSlack,
  } = useSWR("/integrations/slack");

  // -- SWR: Jira integrations --
  const {
    data: jiraEnvelope,
    error: jiraError,
    isLoading: jiraLoading,
    mutate: mutateJira,
  } = useSWR("/integrations/jira");

  const webhooks = (webhooksEnvelope?.data ?? []) as Webhook[];
  const slackIntegrations = (slackEnvelope?.data ?? []) as SlackIntegration[];
  const jiraIntegrations = (jiraEnvelope?.data ?? []) as JiraIntegration[];

  const isLoading = webhooksLoading || slackLoading || jiraLoading;
  const error =
    webhooksError?.message ??
    slackError?.message ??
    jiraError?.message ??
    webhooksEnvelope?.error ??
    slackEnvelope?.error ??
    jiraEnvelope?.error ??
    null;

  const handleRetry = () => {
    mutateWebhooks();
    mutateSlack();
    mutateJira();
  };

  const [actionError, setActionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // -- Delete confirmation state --
  const [deleteTarget, setDeleteTarget] = useState<{
    type: "webhook" | "slack" | "jira";
    id: string;
    label: string;
  } | null>(null);

  // -- Webhook state --
  const [showWebhookModal, setShowWebhookModal] = useState(false);
  const [webhookForm, setWebhookForm] = useState({
    url: "",
    secret: "",
    events: [] as string[],
    description: "",
  });
  const [testingWebhookId, setTestingWebhookId] = useState<string | null>(null);
  const [webhookTestResult, setWebhookTestResult] =
    useState<WebhookTestResult | null>(null);

  const handleAddWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.post("/webhooks", {
        url: webhookForm.url,
        secret: webhookForm.secret || undefined,
        events: webhookForm.events,
        description: webhookForm.description || undefined,
      });
      setShowWebhookModal(false);
      setWebhookForm({ url: "", secret: "", events: [], description: "" });
      mutateWebhooks();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create webhook.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteWebhook = async (webhookId: string) => {
    setActionError(null);
    try {
      await api.delete(`/webhooks/${webhookId}`);
      mutateWebhooks(
        (current: typeof webhooksEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as Webhook[]).filter((w) => w.id !== webhookId),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to delete webhook.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleWebhook = async (
    webhookId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/webhooks/${webhookId}`, {
        is_active: !currentActive,
      });
      mutateWebhooks();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to toggle webhook.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleTestWebhook = async (webhookId: string) => {
    setTestingWebhookId(webhookId);
    setWebhookTestResult(null);
    try {
      const res = await api.post(`/webhooks/${webhookId}/test`);
      setWebhookTestResult(res.data.data as WebhookTestResult);
      mutateWebhooks();
      setTimeout(() => {
        setWebhookTestResult(null);
        setTestingWebhookId(null);
      }, 5000);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setWebhookTestResult({
        status_code: 0,
        response_body: axiosErr.response?.data?.detail ?? "Test failed",
        success: false,
      });
      setTimeout(() => {
        setWebhookTestResult(null);
        setTestingWebhookId(null);
      }, 5000);
    }
  };

  const toggleWebhookEvent = (event: string) => {
    setWebhookForm((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  // -- Slack integration state --
  const [showSlackModal, setShowSlackModal] = useState(false);
  const [slackForm, setSlackForm] = useState({
    webhook_url: "",
    channel_name: "",
    events: [] as string[],
  });
  const [testingSlackId, setTestingSlackId] = useState<string | null>(null);
  const [slackTestResult, setSlackTestResult] =
    useState<SlackTestResult | null>(null);

  const handleAddSlack = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.post("/integrations/slack", {
        webhook_url: slackForm.webhook_url,
        channel_name: slackForm.channel_name || undefined,
        events: slackForm.events,
      });
      setShowSlackModal(false);
      setSlackForm({ webhook_url: "", channel_name: "", events: [] });
      mutateSlack();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ??
          "Failed to create Slack integration.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteSlack = async (integrationId: string) => {
    setActionError(null);
    try {
      await api.delete(`/integrations/slack/${integrationId}`);
      mutateSlack(
        (current: typeof slackEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as SlackIntegration[]).filter(
              (s) => s.id !== integrationId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ??
          "Failed to delete Slack integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleSlack = async (
    integrationId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/integrations/slack/${integrationId}`, {
        is_active: !currentActive,
      });
      mutateSlack();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ??
          "Failed to toggle Slack integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleTestSlack = async (integrationId: string) => {
    setTestingSlackId(integrationId);
    setSlackTestResult(null);
    try {
      const res = await api.post(`/integrations/slack/${integrationId}/test`);
      setSlackTestResult(res.data.data as SlackTestResult);
      setTimeout(() => {
        setSlackTestResult(null);
        setTestingSlackId(null);
      }, 5000);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setSlackTestResult({
        success: false,
        response_body: axiosErr.response?.data?.detail ?? "Test failed",
      });
      setTimeout(() => {
        setSlackTestResult(null);
        setTestingSlackId(null);
      }, 5000);
    }
  };

  const toggleSlackEvent = (event: string) => {
    setSlackForm((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  // -- Jira integration state --
  const [showJiraModal, setShowJiraModal] = useState(false);
  const [jiraForm, setJiraForm] = useState({
    base_url: "",
    email: "",
    api_token: "",
    project_key: "",
    issue_type: "Bug",
  });
  const [testingJiraId, setTestingJiraId] = useState<string | null>(null);
  const [jiraTestResult, setJiraTestResult] = useState<JiraTestResult | null>(
    null,
  );

  const handleAddJira = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.post("/integrations/jira", {
        base_url: jiraForm.base_url,
        email: jiraForm.email,
        api_token: jiraForm.api_token,
        project_key: jiraForm.project_key,
        issue_type: jiraForm.issue_type,
      });
      setShowJiraModal(false);
      setJiraForm({
        base_url: "",
        email: "",
        api_token: "",
        project_key: "",
        issue_type: "Bug",
      });
      mutateJira();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create Jira integration.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteJira = async (integrationId: string) => {
    setActionError(null);
    try {
      await api.delete(`/integrations/jira/${integrationId}`);
      mutateJira(
        (current: typeof jiraEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as JiraIntegration[]).filter(
              (j) => j.id !== integrationId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to delete Jira integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleJira = async (
    integrationId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/integrations/jira/${integrationId}`, {
        is_active: !currentActive,
      });
      mutateJira();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to toggle Jira integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleTestJira = async (integrationId: string) => {
    setTestingJiraId(integrationId);
    setJiraTestResult(null);
    try {
      const res = await api.post(`/integrations/jira/${integrationId}/test`);
      setJiraTestResult(res.data.data as JiraTestResult);
      setTimeout(() => {
        setJiraTestResult(null);
        setTestingJiraId(null);
      }, 5000);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setJiraTestResult({
        success: false,
        message: axiosErr.response?.data?.detail ?? "Test failed",
      });
      setTimeout(() => {
        setJiraTestResult(null);
        setTestingJiraId(null);
      }, 5000);
    }
  };

  const SUB_TABS: { key: IntegrationTab; label: string }[] = [
    { key: "webhooks", label: "Webhooks" },
    { key: "slack", label: "Slack" },
    { key: "jira", label: "Jira" },
  ];

  return (
    <>
      {/* Sub-tab navigation */}
      <div className="flex items-center gap-2">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                : "text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error state for initial load */}
      {error && <ErrorState message={error} onRetry={handleRetry} />}

      {/* Action error banner */}
      {actionError && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {actionError}
        </div>
      )}

      {!error && (
        <>
          {/* Webhooks */}
          {activeTab === "webhooks" && (
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Webhooks
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Receive HTTP notifications when events occur
                  </p>
                </div>
                <button
                  onClick={() => setShowWebhookModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Add Webhook
                </button>
              </div>

              {webhooksLoading ? (
                <div className="flex h-48 items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
                </div>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {webhooks.map((wh) => (
                    <div
                      key={wh.id}
                      className="flex items-center justify-between px-6 py-4"
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            wh.is_active ? "bg-green-400" : "bg-gray-300"
                          }`}
                          title={wh.is_active ? "Active" : "Inactive"}
                        />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {wh.description || wh.url}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                            <Globe size={12} />
                            <span className="max-w-xs truncate font-mono text-xs">
                              {wh.url}
                            </span>
                            {wh.events.map((ev) => (
                              <span
                                key={ev}
                                className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                              >
                                {ev}
                              </span>
                            ))}
                            {wh.last_triggered_at && (
                              <span className="text-xs">
                                Last:{" "}
                                {new Date(
                                  wh.last_triggered_at,
                                ).toLocaleString()}
                                {wh.last_status_code !== null && (
                                  <span
                                    className={`ml-1 ${
                                      wh.last_status_code >= 200 &&
                                      wh.last_status_code < 300
                                        ? "text-green-600"
                                        : "text-red-600"
                                    }`}
                                  >
                                    ({wh.last_status_code})
                                  </span>
                                )}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {testingWebhookId === wh.id && webhookTestResult && (
                          <span
                            className={`text-xs ${
                              webhookTestResult.success
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {webhookTestResult.success
                              ? "OK"
                              : `Failed (${webhookTestResult.status_code})`}
                          </span>
                        )}
                        <button
                          onClick={() => handleTestWebhook(wh.id)}
                          disabled={testingWebhookId === wh.id}
                          className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                          title="Send test payload"
                        >
                          <Send size={14} />
                          Test
                        </button>
                        <button
                          onClick={() =>
                            handleToggleWebhook(wh.id, wh.is_active)
                          }
                          className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                            wh.is_active
                              ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                              : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                          }`}
                          title={
                            wh.is_active ? "Disable webhook" : "Enable webhook"
                          }
                        >
                          <Check size={14} />
                          {wh.is_active ? "Disable" : "Enable"}
                        </button>
                        <button
                          onClick={() =>
                            setDeleteTarget({
                              type: "webhook",
                              id: wh.id,
                              label: wh.description || wh.url,
                            })
                          }
                          className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                          title="Remove webhook"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                  {webhooks.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                      <Globe size={20} className="mb-2" />
                      <p className="text-sm">No webhooks configured.</p>
                      <p className="mt-1 text-sm">
                        Add a webhook to receive event notifications.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Slack Integration */}
          {activeTab === "slack" && (
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Slack Integration
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Send security notifications to Slack channels
                  </p>
                </div>
                <button
                  onClick={() => setShowSlackModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Add Slack Integration
                </button>
              </div>

              {slackLoading ? (
                <div className="flex h-48 items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
                </div>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {slackIntegrations.map((si) => (
                    <div
                      key={si.id}
                      className="flex items-center justify-between px-6 py-4"
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            si.is_active ? "bg-green-400" : "bg-gray-300"
                          }`}
                          title={si.is_active ? "Active" : "Inactive"}
                        />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {si.channel_name || "Slack Webhook"}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                            <MessageSquare size={12} />
                            <span className="max-w-xs truncate font-mono text-xs">
                              {si.webhook_url.replace(
                                /^(https:\/\/hooks\.slack\.com\/services\/T[^/]+\/).*/,
                                "$1...",
                              )}
                            </span>
                            {si.events.map((ev) => (
                              <span
                                key={ev}
                                className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                              >
                                {ev}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {testingSlackId === si.id && slackTestResult && (
                          <span
                            className={`text-xs ${
                              slackTestResult.success
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {slackTestResult.success ? "OK" : "Failed"}
                          </span>
                        )}
                        <button
                          onClick={() => handleTestSlack(si.id)}
                          disabled={testingSlackId === si.id}
                          className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                          title="Send test message"
                        >
                          <Send size={14} />
                          Test
                        </button>
                        <button
                          onClick={() => handleToggleSlack(si.id, si.is_active)}
                          className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                            si.is_active
                              ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                              : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                          }`}
                          title={si.is_active ? "Disable" : "Enable"}
                        >
                          <Check size={14} />
                          {si.is_active ? "Disable" : "Enable"}
                        </button>
                        <button
                          onClick={() =>
                            setDeleteTarget({
                              type: "slack",
                              id: si.id,
                              label: si.channel_name || "Slack Webhook",
                            })
                          }
                          className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                          title="Remove Slack integration"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                  {slackIntegrations.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                      <MessageSquare size={20} className="mb-2" />
                      <p className="text-sm">
                        No Slack integrations configured.
                      </p>
                      <p className="mt-1 text-sm">
                        Add a Slack integration to receive security
                        notifications.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Jira Integration */}
          {activeTab === "jira" && (
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Jira Integration
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Create Jira tickets from security findings
                  </p>
                </div>
                <button
                  onClick={() => setShowJiraModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Add Jira Integration
                </button>
              </div>

              {jiraLoading ? (
                <div className="flex h-48 items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
                </div>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {jiraIntegrations.map((ji) => (
                    <div
                      key={ji.id}
                      className="flex items-center justify-between px-6 py-4"
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            ji.is_active ? "bg-green-400" : "bg-gray-300"
                          }`}
                          title={ji.is_active ? "Active" : "Inactive"}
                        />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {ji.project_key} ({ji.issue_type})
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                            <Globe size={12} />
                            <span className="max-w-xs truncate font-mono text-xs">
                              {ji.base_url}
                            </span>
                            <span className="text-xs">{ji.email}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {testingJiraId === ji.id && jiraTestResult && (
                          <span
                            className={`text-xs ${
                              jiraTestResult.success
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {jiraTestResult.success
                              ? jiraTestResult.message
                              : jiraTestResult.message}
                          </span>
                        )}
                        <button
                          onClick={() => handleTestJira(ji.id)}
                          disabled={testingJiraId === ji.id}
                          className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                          title="Test Jira connection"
                        >
                          <Send size={14} />
                          Test
                        </button>
                        <button
                          onClick={() => handleToggleJira(ji.id, ji.is_active)}
                          className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                            ji.is_active
                              ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                              : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                          }`}
                          title={ji.is_active ? "Disable" : "Enable"}
                        >
                          <Check size={14} />
                          {ji.is_active ? "Disable" : "Enable"}
                        </button>
                        <button
                          onClick={() =>
                            setDeleteTarget({
                              type: "jira",
                              id: ji.id,
                              label: `${ji.project_key} (${ji.base_url})`,
                            })
                          }
                          className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                          title="Remove Jira integration"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                  {jiraIntegrations.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                      <Globe size={20} className="mb-2" />
                      <p className="text-sm">
                        No Jira integrations configured.
                      </p>
                      <p className="mt-1 text-sm">
                        Add a Jira integration to create tickets from findings.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Add Webhook Modal */}
      <Modal
        isOpen={showWebhookModal}
        onClose={() => {
          setShowWebhookModal(false);
          setWebhookForm({
            url: "",
            secret: "",
            events: [],
            description: "",
          });
          setFormError(null);
        }}
        title="Add Webhook"
      >
        <form onSubmit={handleAddWebhook} className="space-y-4">
          <div>
            <label
              htmlFor="wh_url"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Webhook URL
            </label>
            <input
              id="wh_url"
              type="url"
              required
              value={webhookForm.url}
              onChange={(e) =>
                setWebhookForm((p) => ({ ...p, url: e.target.value }))
              }
              placeholder="https://example.com/webhook"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>

          <div>
            <label
              htmlFor="wh_desc"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Description (optional)
            </label>
            <input
              id="wh_desc"
              type="text"
              value={webhookForm.description}
              onChange={(e) =>
                setWebhookForm((p) => ({
                  ...p,
                  description: e.target.value,
                }))
              }
              placeholder="Slack notification channel"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Events
            </label>
            <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
              Select which events trigger this webhook
            </p>
            <div className="space-y-2">
              {ALLOWED_EVENTS.map((ev) => (
                <label
                  key={ev}
                  className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
                >
                  <input
                    type="checkbox"
                    checked={webhookForm.events.includes(ev)}
                    onChange={() => toggleWebhookEvent(ev)}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="font-mono text-xs">{ev}</span>
                  <span className="text-xs text-gray-400">
                    {ev === "scan.completed" && "- Scan finished successfully"}
                    {ev === "scan.failed" && "- Scan encountered an error"}
                    {ev === "finding.high" &&
                      "- High-severity findings detected"}
                    {ev === "finding.critical_change" &&
                      "- Critical finding status changed"}
                  </span>
                </label>
              ))}
            </div>
            {webhookForm.events.length === 0 && (
              <p className="mt-1 text-xs text-red-500">
                Select at least one event.
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="wh_secret"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Signing Secret (optional)
            </label>
            <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
              Used to generate HMAC-SHA256 signature header
            </p>
            <input
              id="wh_secret"
              type="password"
              value={webhookForm.secret}
              onChange={(e) =>
                setWebhookForm((p) => ({ ...p, secret: e.target.value }))
              }
              placeholder="your-signing-secret"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>

          {formError && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowWebhookModal(false);
                setWebhookForm({
                  url: "",
                  secret: "",
                  events: [],
                  description: "",
                });
                setFormError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={webhookForm.events.length === 0}
              loading={isSubmitting}
            >
              Create Webhook
            </Button>
          </div>
        </form>
      </Modal>

      {/* Add Slack Integration Modal */}
      <Modal
        isOpen={showSlackModal}
        onClose={() => {
          setShowSlackModal(false);
          setSlackForm({
            webhook_url: "",
            channel_name: "",
            events: [],
          });
          setFormError(null);
        }}
        title="Add Slack Integration"
      >
        <form onSubmit={handleAddSlack} className="space-y-4">
          <div>
            <label
              htmlFor="slack_url"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Slack Webhook URL
            </label>
            <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
              Create an Incoming Webhook in your Slack workspace settings
            </p>
            <input
              id="slack_url"
              type="url"
              required
              value={slackForm.webhook_url}
              onChange={(e) =>
                setSlackForm((p) => ({
                  ...p,
                  webhook_url: e.target.value,
                }))
              }
              placeholder="https://hooks.slack.com/services/T.../B.../..."
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>

          <div>
            <label
              htmlFor="slack_channel"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Channel Name (display only)
            </label>
            <div className="relative mt-1">
              <Hash
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
              />
              <input
                id="slack_channel"
                type="text"
                value={slackForm.channel_name}
                onChange={(e) =>
                  setSlackForm((p) => ({
                    ...p,
                    channel_name: e.target.value,
                  }))
                }
                placeholder="security-alerts"
                className="w-full rounded-lg border border-gray-300 py-2 pl-8 pr-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Events
            </label>
            <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
              Select which events trigger Slack notifications
            </p>
            <div className="space-y-2">
              {SLACK_EVENTS.map((ev) => (
                <label
                  key={ev}
                  className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
                >
                  <input
                    type="checkbox"
                    checked={slackForm.events.includes(ev)}
                    onChange={() => toggleSlackEvent(ev)}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="font-mono text-xs">{ev}</span>
                  <span className="text-xs text-gray-400">
                    {ev === "scan.completed" && "- Scan finished successfully"}
                    {ev === "scan.failed" && "- Scan encountered an error"}
                    {ev === "finding.high" &&
                      "- High-severity findings detected"}
                    {ev === "finding.critical_change" &&
                      "- Critical finding status changed"}
                  </span>
                </label>
              ))}
            </div>
            {slackForm.events.length === 0 && (
              <p className="mt-1 text-xs text-red-500">
                Select at least one event.
              </p>
            )}
          </div>

          {formError && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowSlackModal(false);
                setSlackForm({
                  webhook_url: "",
                  channel_name: "",
                  events: [],
                });
                setFormError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={slackForm.events.length === 0}
              loading={isSubmitting}
            >
              Add Integration
            </Button>
          </div>
        </form>
      </Modal>

      {/* Add Jira Integration Modal */}
      <Modal
        isOpen={showJiraModal}
        onClose={() => {
          setShowJiraModal(false);
          setJiraForm({
            base_url: "",
            email: "",
            api_token: "",
            project_key: "",
            issue_type: "Bug",
          });
          setFormError(null);
        }}
        title="Add Jira Integration"
      >
        <form onSubmit={handleAddJira} className="space-y-4">
          <div>
            <label
              htmlFor="jira_base_url"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Jira Base URL
            </label>
            <input
              id="jira_base_url"
              type="url"
              required
              value={jiraForm.base_url}
              onChange={(e) =>
                setJiraForm((p) => ({ ...p, base_url: e.target.value }))
              }
              placeholder="https://yourcompany.atlassian.net"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>
          <div>
            <label
              htmlFor="jira_email"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Email
            </label>
            <input
              id="jira_email"
              type="email"
              required
              value={jiraForm.email}
              onChange={(e) =>
                setJiraForm((p) => ({ ...p, email: e.target.value }))
              }
              placeholder="user@company.com"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>
          <div>
            <label
              htmlFor="jira_api_token"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              API Token
            </label>
            <input
              id="jira_api_token"
              type="password"
              required
              value={jiraForm.api_token}
              onChange={(e) =>
                setJiraForm((p) => ({ ...p, api_token: e.target.value }))
              }
              placeholder="••••••••••••"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>
          <div>
            <label
              htmlFor="jira_project_key"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Project Key
            </label>
            <input
              id="jira_project_key"
              type="text"
              required
              value={jiraForm.project_key}
              onChange={(e) =>
                setJiraForm((p) => ({ ...p, project_key: e.target.value }))
              }
              placeholder="SEC"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            />
          </div>
          <div>
            <label
              htmlFor="jira_issue_type"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Issue Type
            </label>
            <select
              id="jira_issue_type"
              value={jiraForm.issue_type}
              onChange={(e) =>
                setJiraForm((p) => ({ ...p, issue_type: e.target.value }))
              }
              className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
            >
              {JIRA_ISSUE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {formError && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowJiraModal(false);
                setJiraForm({
                  base_url: "",
                  email: "",
                  api_token: "",
                  project_key: "",
                  issue_type: "Bug",
                });
                setFormError(null);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={isSubmitting}>
              Add Integration
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            if (deleteTarget.type === "webhook") {
              handleDeleteWebhook(deleteTarget.id);
            } else if (deleteTarget.type === "slack") {
              handleDeleteSlack(deleteTarget.id);
            } else {
              handleDeleteJira(deleteTarget.id);
            }
            setDeleteTarget(null);
          }
        }}
        title={`Remove ${deleteTarget?.type === "webhook" ? "Webhook" : deleteTarget?.type === "slack" ? "Slack Integration" : "Jira Integration"}`}
        message={`Remove "${deleteTarget?.label ?? ""}"? This action cannot be undone.`}
        confirmLabel="Remove"
      />
    </>
  );
}
