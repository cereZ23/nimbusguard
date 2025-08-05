"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Shield,
  Clock,
  FileText,
  ShieldCheck,
  Server,
  ExternalLink,
  Lightbulb,
  UserPlus,
  MessageSquare,
  Trash2,
  Send,
  History,
  ArrowRightLeft,
  UserCheck,
  UserMinus,
  ShieldAlert,
  MessageCircle,
  Layers,
  Copy,
  Check,
  Code,
  Terminal,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import SeverityBadge from "@/components/ui/severity-badge";
import StatusBadge from "@/components/ui/status-badge";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  FindingComment,
  FindingEvent,
  SimilarFinding,
  TenantUser,
} from "@/types";

interface FindingDetailData {
  id: string;
  status: string;
  severity: string;
  title: string;
  dedup_key: string;
  waived: boolean;
  first_detected_at: string;
  last_evaluated_at: string;
  cloud_account_id: string;
  asset_id: string | null;
  control_id: string | null;
  assigned_to: string | null;
  assignee_email: string | null;
  assignee_name: string | null;
  asset: {
    id: string;
    name: string;
    resource_type: string;
    region: string | null;
    provider_id?: string;
  } | null;
  control: {
    id: string;
    code: string;
    name: string;
    severity: string;
    framework: string;
    remediation_hint?: string;
  } | null;
  evidences: Array<{
    id: string;
    snapshot: Record<string, unknown>;
    collected_at: string;
  }>;
}

// ── Remediation types & component ────────────────────────────────────

interface RemediationData {
  control_code: string;
  control_name: string;
  description: string | null;
  remediation_hint: string | null;
  snippets: {
    terraform: string | null;
    bicep: string | null;
    azure_cli: string | null;
  };
}

type SnippetTab = "terraform" | "bicep" | "azure_cli";

const TAB_CONFIG: { key: SnippetTab; label: string; icon: React.ReactNode }[] =
  [
    {
      key: "terraform",
      label: "Terraform",
      icon: <Code className="h-3.5 w-3.5" />,
    },
    { key: "bicep", label: "Bicep", icon: <Code className="h-3.5 w-3.5" /> },
    {
      key: "azure_cli",
      label: "Azure CLI",
      icon: <Terminal className="h-3.5 w-3.5" />,
    },
  ];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
      title="Copy to clipboard"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-green-600 dark:text-green-400" />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          Copy
        </>
      )}
    </button>
  );
}

function RemediationPanel({
  remediation,
  fallbackHint,
}: {
  remediation: RemediationData | null;
  fallbackHint?: string;
}) {
  const [activeTab, setActiveTab] = useState<SnippetTab>("terraform");

  const hasSnippets =
    remediation &&
    (remediation.snippets.terraform ||
      remediation.snippets.bicep ||
      remediation.snippets.azure_cli);

  // Determine available tabs
  const availableTabs = hasSnippets
    ? TAB_CONFIG.filter((tab) => remediation.snippets[tab.key])
    : [];

  // Auto-select first available tab
  const effectiveTab = availableTabs.some((t) => t.key === activeTab)
    ? activeTab
    : (availableTabs[0]?.key ?? "terraform");

  const activeSnippet = remediation?.snippets[effectiveTab] ?? null;

  // If no remediation data at all, fall back to hint
  if (!remediation && !fallbackHint) return null;

  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50 shadow-sm dark:border-emerald-800 dark:bg-emerald-900/20">
      {/* Header */}
      <div className="px-5 pt-5 pb-3">
        <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-emerald-800 dark:text-emerald-300">
          <Lightbulb className="h-4 w-4 flex-shrink-0" />
          Remediation Guidance
        </h2>
        {remediation?.description && (
          <p className="text-sm text-emerald-700 dark:text-emerald-300">
            {remediation.description}
          </p>
        )}
        {/* Always show the text hint if available */}
        {(remediation?.remediation_hint || fallbackHint) && (
          <p className="mt-2 text-sm text-emerald-900 dark:text-emerald-200 leading-relaxed">
            {remediation?.remediation_hint ?? fallbackHint}
          </p>
        )}
      </div>

      {/* Tabbed IaC snippets */}
      {hasSnippets && availableTabs.length > 0 && (
        <div className="px-5 pb-5">
          {/* Tabs */}
          <div className="mt-3 flex gap-1 rounded-lg bg-emerald-100/70 p-1 dark:bg-emerald-900/30">
            {availableTabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  effectiveTab === tab.key
                    ? "bg-white text-emerald-800 shadow-sm dark:bg-gray-800 dark:text-emerald-300"
                    : "text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-200"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Code block */}
          {activeSnippet && (
            <div className="mt-3 rounded-lg border border-emerald-200 bg-gray-900 dark:border-emerald-700">
              <div className="flex items-center justify-between border-b border-gray-700 px-3 py-2">
                <span className="text-xs font-medium text-gray-400">
                  {availableTabs.find((t) => t.key === effectiveTab)?.label}
                </span>
                <CopyButton text={activeSnippet} />
              </div>
              <pre className="max-h-80 overflow-auto p-4 text-xs leading-relaxed text-gray-100">
                <code>{activeSnippet}</code>
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Timeline helpers ─────────────────────────────────────────────────

function getEventIcon(eventType: string) {
  switch (eventType) {
    case "status_change":
      return <ArrowRightLeft className="h-3.5 w-3.5" />;
    case "severity_change":
      return <ShieldAlert className="h-3.5 w-3.5" />;
    case "assigned":
      return <UserCheck className="h-3.5 w-3.5" />;
    case "unassigned":
      return <UserMinus className="h-3.5 w-3.5" />;
    case "commented":
      return <MessageCircle className="h-3.5 w-3.5" />;
    case "waiver_requested":
      return <ShieldCheck className="h-3.5 w-3.5" />;
    case "waiver_approved":
      return <ShieldCheck className="h-3.5 w-3.5" />;
    default:
      return <Clock className="h-3.5 w-3.5" />;
  }
}

function getEventColor(eventType: string): string {
  switch (eventType) {
    case "status_change":
      return "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400";
    case "severity_change":
      return "bg-orange-100 text-orange-600 dark:bg-orange-900/40 dark:text-orange-400";
    case "assigned":
      return "bg-green-100 text-green-600 dark:bg-green-900/40 dark:text-green-400";
    case "unassigned":
      return "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400";
    case "commented":
      return "bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-400";
    case "waiver_requested":
      return "bg-purple-100 text-purple-600 dark:bg-purple-900/40 dark:text-purple-400";
    case "waiver_approved":
      return "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400";
    default:
      return "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400";
  }
}

function formatEventDescription(event: FindingEvent): string {
  const actor = event.user_email ?? "System";

  switch (event.event_type) {
    case "status_change":
      return `Status changed from ${event.old_value ?? "unknown"} to ${event.new_value ?? "unknown"} by ${actor}`;
    case "severity_change":
      return `Severity changed from ${event.old_value ?? "unknown"} to ${event.new_value ?? "unknown"} by ${actor}`;
    case "assigned":
      return `Assigned by ${actor}`;
    case "unassigned":
      return `Unassigned by ${actor}`;
    case "commented":
      return `${actor} added a comment`;
    case "waiver_requested":
      return `Waiver requested by ${actor}`;
    case "waiver_approved":
      return `Waiver approved by ${actor}`;
    default:
      return `${event.event_type} by ${actor}`;
  }
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function TimelineItem({ event }: { event: FindingEvent }) {
  return (
    <div className="relative flex gap-3 pl-0">
      {/* Dot / icon */}
      <div
        className={`relative z-10 flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-full ${getEventColor(event.event_type)}`}
      >
        {getEventIcon(event.event_type)}
      </div>

      {/* Content */}
      <div className="flex-1 pt-1">
        <p className="text-sm text-gray-800 dark:text-gray-200">
          {formatEventDescription(event)}
        </p>
        {event.details && event.event_type !== "commented" && (
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 truncate max-w-md">
            {event.details}
          </p>
        )}
        <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
          {formatRelativeTime(event.created_at)}
        </p>
      </div>
    </div>
  );
}

// ── Main page component ──────────────────────────────────────────────

export default function FindingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [finding, setFinding] = useState<FindingDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Waiver state
  const [showWaiverForm, setShowWaiverForm] = useState(false);
  const [waiverReason, setWaiverReason] = useState("");
  const [waiverSubmitting, setWaiverSubmitting] = useState(false);
  const [waiverSuccess, setWaiverSuccess] = useState(false);
  const [waiverError, setWaiverError] = useState<string | null>(null);

  // Assignment state
  const [tenantUsers, setTenantUsers] = useState<TenantUser[]>([]);
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  // Comments state
  const [comments, setComments] = useState<FindingComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);

  // Timeline state
  const [timelineEvents, setTimelineEvents] = useState<FindingEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);

  // Similar findings state
  const [similarFindings, setSimilarFindings] = useState<SimilarFinding[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);

  // Remediation snippets state
  const [remediation, setRemediation] = useState<RemediationData | null>(null);

  const isAdmin = user?.role === "admin";

  const fetchFindingDetail = useCallback(() => {
    if (!id) return;
    setError(null);
    setIsLoading(true);

    api
      .get(`/findings/${id}`)
      .then((res) => {
        setFinding(res.data?.data as FindingDetailData);
      })
      .catch((err) => {
        setError(err?.response?.data?.error ?? "Failed to load finding");
      })
      .finally(() => setIsLoading(false));
  }, [id]);

  const fetchComments = useCallback(() => {
    if (!id) return;
    setCommentsLoading(true);

    api
      .get(`/findings/${id}/comments`)
      .then((res) => {
        setComments((res.data?.data as FindingComment[]) ?? []);
      })
      .catch(() => {
        // Silently fail for comments — not critical
      })
      .finally(() => setCommentsLoading(false));
  }, [id]);

  const fetchTenantUsers = useCallback(() => {
    api
      .get("/users")
      .then((res) => {
        setTenantUsers((res.data?.data as TenantUser[]) ?? []);
      })
      .catch(() => {
        // Silently fail — assignment dropdown just won't populate
      });
  }, []);

  const fetchTimeline = useCallback(() => {
    if (!id) return;
    setTimelineLoading(true);

    api
      .get(`/findings/${id}/timeline`)
      .then((res) => {
        setTimelineEvents((res.data?.data as FindingEvent[]) ?? []);
      })
      .catch(() => {
        // Silently fail for timeline — not critical
      })
      .finally(() => setTimelineLoading(false));
  }, [id]);

  const fetchSimilarFindings = useCallback(() => {
    if (!id) return;
    setSimilarLoading(true);

    api
      .get(`/findings/${id}/similar`)
      .then((res) => {
        setSimilarFindings((res.data?.data as SimilarFinding[]) ?? []);
      })
      .catch(() => {
        // Silently fail for similar findings — not critical
      })
      .finally(() => setSimilarLoading(false));
  }, [id]);

  const fetchRemediation = useCallback(() => {
    if (!id) return;

    api
      .get(`/findings/${id}/remediation`)
      .then((res) => {
        setRemediation((res.data?.data as RemediationData) ?? null);
      })
      .catch(() => {
        // Silently fail — remediation snippets are optional
      });
  }, [id]);

  useEffect(() => {
    fetchFindingDetail();
    fetchComments();
    fetchTenantUsers();
    fetchTimeline();
    fetchSimilarFindings();
    fetchRemediation();
  }, [
    fetchFindingDetail,
    fetchComments,
    fetchTenantUsers,
    fetchTimeline,
    fetchSimilarFindings,
    fetchRemediation,
  ]);

  const handleWaiverSubmit = async () => {
    if (!waiverReason.trim() || !id) return;
    setWaiverSubmitting(true);
    setWaiverError(null);

    try {
      await api.post(`/findings/${id}/exception`, {
        reason: waiverReason,
      });
      setWaiverSuccess(true);
      setShowWaiverForm(false);
      setWaiverReason("");
      fetchTimeline();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setWaiverError(
        axiosErr.response?.data?.detail ?? "Failed to submit waiver request",
      );
    } finally {
      setWaiverSubmitting(false);
    }
  };

  const handleAssign = async (userId: string | null) => {
    if (!id) return;
    setAssignLoading(true);
    setAssignError(null);

    try {
      const res = await api.put(`/findings/${id}/assign`, {
        user_id: userId,
      });
      const updated = res.data?.data;
      if (updated && finding) {
        setFinding({
          ...finding,
          assigned_to: updated.assigned_to,
          assignee_email: updated.assignee_email,
          assignee_name: updated.assignee_name,
        });
      }
      fetchTimeline();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setAssignError(
        axiosErr.response?.data?.detail ?? "Failed to assign finding",
      );
    } finally {
      setAssignLoading(false);
    }
  };

  const handleAddComment = async () => {
    if (!newComment.trim() || !id) return;
    setCommentSubmitting(true);
    setCommentError(null);

    try {
      await api.post(`/findings/${id}/comments`, {
        content: newComment.trim(),
      });
      setNewComment("");
      fetchComments();
      fetchTimeline();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setCommentError(
        axiosErr.response?.data?.detail ?? "Failed to add comment",
      );
    } finally {
      setCommentSubmitting(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!id) return;

    try {
      await api.delete(`/findings/${id}/comments/${commentId}`);
      fetchComments();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setCommentError(
        axiosErr.response?.data?.detail ?? "Failed to delete comment",
      );
    }
  };

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex h-96 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      </AppShell>
    );
  }

  if (error || !finding) {
    return (
      <AppShell>
        <ErrorState
          message={error ?? "Finding not found"}
          onRetry={error ? fetchFindingDetail : undefined}
        />
        <div className="mt-2 text-center">
          <button
            onClick={() => router.push("/findings")}
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            Back to Findings
          </button>
        </div>
      </AppShell>
    );
  }

  const azurePortalUrl = finding.asset?.provider_id
    ? `https://portal.azure.com/#@/resource${finding.asset.provider_id}`
    : null;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Back + header */}
        <div>
          <button
            onClick={() => router.push("/findings")}
            className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Findings
          </button>

          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {finding.title}
                </h1>
                <SeverityBadge severity={finding.severity} />
                <StatusBadge status={finding.status} />
                {finding.waived && (
                  <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-semibold text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                    WAIVED
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-gray-400 font-mono dark:text-gray-500">
                {finding.dedup_key}
              </p>
            </div>

            {/* Request Waiver button */}
            {finding.status === "fail" && !finding.waived && !waiverSuccess && (
              <button
                onClick={() => setShowWaiverForm(!showWaiverForm)}
                className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-purple-700"
              >
                <ShieldCheck className="mr-1.5 inline h-4 w-4" />
                Request Waiver
              </button>
            )}
            {waiverSuccess && (
              <span className="rounded-lg bg-green-100 px-4 py-2 text-sm font-medium text-green-700">
                Waiver Requested
              </span>
            )}
          </div>
        </div>

        {/* Waiver form */}
        {showWaiverForm && (
          <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 shadow-sm dark:border-purple-900 dark:bg-purple-950">
            <h3 className="mb-2 text-sm font-medium text-purple-800 dark:text-purple-200">
              Request a Waiver
            </h3>
            <p className="mb-3 text-xs text-purple-600 dark:text-purple-400">
              Provide a reason for waiving this finding. An admin will review
              your request.
            </p>
            <textarea
              value={waiverReason}
              onChange={(e) => setWaiverReason(e.target.value)}
              placeholder="Reason for waiver request..."
              className="w-full rounded-lg border border-purple-200 bg-white px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-purple-700 dark:bg-gray-900 dark:text-white dark:placeholder:text-gray-500 dark:focus:border-purple-600"
              rows={3}
            />
            {waiverError && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                {waiverError}
              </p>
            )}
            <div className="mt-2 flex gap-2">
              <button
                onClick={handleWaiverSubmit}
                disabled={!waiverReason.trim() || waiverSubmitting}
                className="rounded-lg bg-purple-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-purple-700 disabled:opacity-50 dark:bg-purple-700 dark:hover:bg-purple-600"
              >
                {waiverSubmitting ? "Submitting..." : "Submit Request"}
              </button>
              <button
                onClick={() => setShowWaiverForm(false)}
                className="rounded-lg border border-gray-300 bg-white px-4 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Assignment section */}
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
            <UserPlus className="h-4 w-4" />
            Assignment
          </h2>
          <div className="flex items-center gap-3">
            {finding.assigned_to ? (
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                  {(finding.assignee_name ?? finding.assignee_email ?? "?")
                    .charAt(0)
                    .toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    {finding.assignee_name ?? "Unknown"}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {finding.assignee_email ?? ""}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Unassigned
              </p>
            )}

            {isAdmin && (
              <div className="ml-auto flex items-center gap-2">
                <select
                  className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                  value={finding.assigned_to ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    handleAssign(val || null);
                  }}
                  disabled={assignLoading}
                >
                  <option value="">-- Unassigned --</option>
                  {tenantUsers
                    .filter((u) => u.is_active)
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name} ({u.email})
                      </option>
                    ))}
                </select>
                {assignLoading && (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                )}
              </div>
            )}
          </div>
          {assignError && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              {assignError}
            </p>
          )}
        </div>

        {/* Info grid */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Clock className="h-4 w-4" />
              First Detected
            </div>
            <p className="mt-1 font-medium text-gray-900 dark:text-white">
              {new Date(finding.first_detected_at).toLocaleDateString()}
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Clock className="h-4 w-4" />
              Last Evaluated
            </div>
            <p className="mt-1 font-medium text-gray-900 dark:text-white">
              {new Date(finding.last_evaluated_at).toLocaleDateString()}
            </p>
          </div>

          {/* Asset card */}
          {finding.asset && (
            <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div
                onClick={() => router.push(`/assets/${finding.asset!.id}`)}
                className="cursor-pointer transition-colors hover:text-blue-700 dark:hover:text-blue-400"
              >
                <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                  <Server className="h-4 w-4" />
                  Asset
                </div>
                <p className="mt-1 font-medium text-blue-700 dark:text-blue-400">
                  {finding.asset.name}
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {finding.asset.region ?? "\u2014"}
                </p>
              </div>
              {azurePortalUrl && (
                <a
                  href={azurePortalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="mt-2 inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-600 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:border-blue-600 dark:hover:text-blue-400"
                >
                  <ExternalLink className="h-3 w-3" />
                  Open in Azure Portal
                </a>
              )}
            </div>
          )}

          {/* Control card */}
          {finding.control && (
            <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <Shield className="h-4 w-4" />
                Control
              </div>
              <p className="mt-1 font-medium text-gray-900 dark:text-white">
                {finding.control.code}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {finding.control.name}
              </p>
            </div>
          )}
        </div>

        {/* Evidence */}
        {finding.evidences.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50">
              <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
                <FileText className="h-4 w-4" />
                Evidence ({finding.evidences.length})
              </h2>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {finding.evidences.map((ev) => (
                <div key={ev.id} className="p-4">
                  <p className="mb-2 text-xs text-gray-400 dark:text-gray-500">
                    Collected: {new Date(ev.collected_at).toLocaleString()}
                  </p>
                  <pre className="max-h-64 overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                    {JSON.stringify(ev.snapshot, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Remediation */}
        {(remediation || finding.control?.remediation_hint) && (
          <RemediationPanel
            remediation={remediation}
            fallbackHint={finding.control?.remediation_hint}
          />
        )}

        {/* Similar findings section */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50">
            <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
              <Layers className="h-4 w-4" />
              Similar Findings ({similarFindings.length})
            </h2>
          </div>

          <div className="p-4">
            {similarLoading && similarFindings.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
              </div>
            ) : similarFindings.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400 dark:text-gray-500">
                No similar findings
              </div>
            ) : (
              <div className="space-y-4">
                {/* Same control group */}
                {similarFindings.some(
                  (sf) => sf.similarity_type === "same_control",
                ) && (
                  <div>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Same control -- other resources
                    </h3>
                    <div className="divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-700 dark:border-gray-700">
                      {similarFindings
                        .filter((sf) => sf.similarity_type === "same_control")
                        .map((sf) => (
                          <div
                            key={sf.id}
                            className="flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50"
                          >
                            <SeverityBadge severity={sf.severity} />
                            <button
                              onClick={() =>
                                router.push(`/assets/${sf.asset_id}`)
                              }
                              className="min-w-0 flex-1 truncate text-left text-sm font-medium text-blue-700 hover:underline dark:text-blue-400"
                              title={sf.asset_name}
                            >
                              {sf.asset_name}
                            </button>
                            <span className="hidden text-xs text-gray-500 dark:text-gray-400 sm:inline">
                              {sf.control_code}
                            </span>
                            <StatusBadge status={sf.status} />
                            <button
                              onClick={() => router.push(`/findings/${sf.id}`)}
                              className="flex-shrink-0 rounded px-2 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-600 dark:hover:text-white"
                            >
                              View
                            </button>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* Same asset group */}
                {similarFindings.some(
                  (sf) => sf.similarity_type === "same_asset",
                ) && (
                  <div>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                      Same resource -- other controls
                    </h3>
                    <div className="divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-700 dark:border-gray-700">
                      {similarFindings
                        .filter((sf) => sf.similarity_type === "same_asset")
                        .map((sf) => (
                          <div
                            key={sf.id}
                            className="flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50"
                          >
                            <SeverityBadge severity={sf.severity} />
                            <div className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium text-gray-900 dark:text-white">
                                {sf.control_code}
                              </span>
                              <span className="block truncate text-xs text-gray-500 dark:text-gray-400">
                                {sf.control_name}
                              </span>
                            </div>
                            <StatusBadge status={sf.status} />
                            <button
                              onClick={() => router.push(`/findings/${sf.id}`)}
                              className="flex-shrink-0 rounded px-2 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-600 dark:hover:text-white"
                            >
                              View
                            </button>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Timeline section */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50">
            <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
              <History className="h-4 w-4" />
              Timeline ({timelineEvents.length})
            </h2>
          </div>

          <div className="p-4">
            {timelineLoading && timelineEvents.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
              </div>
            ) : timelineEvents.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400 dark:text-gray-500">
                No timeline events yet
              </div>
            ) : (
              <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-[15px] top-2 bottom-2 w-px bg-gray-200 dark:bg-gray-700" />

                <div className="space-y-4">
                  {timelineEvents.map((event) => (
                    <TimelineItem key={event.id} event={event} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Comments section */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50">
            <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
              <MessageSquare className="h-4 w-4" />
              Comments ({comments.length})
            </h2>
          </div>

          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {commentsLoading && comments.length === 0 ? (
              <div className="flex items-center justify-center p-8">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
              </div>
            ) : comments.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400 dark:text-gray-500">
                No comments yet
              </div>
            ) : (
              comments.map((comment) => (
                <div key={comment.id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                        {(comment.user_name ?? comment.user_email ?? "?")
                          .charAt(0)
                          .toUpperCase()}
                      </div>
                      <div>
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {comment.user_name ?? "Unknown"}
                        </span>
                        {comment.user_email && (
                          <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
                            {comment.user_email}
                          </span>
                        )}
                        <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
                          {new Date(comment.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>

                    {/* Delete button — only for own comments or admin */}
                    {(comment.user_id === user?.id || isAdmin) && (
                      <button
                        onClick={() => handleDeleteComment(comment.id)}
                        className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20 dark:hover:text-red-400"
                        title="Delete comment"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                  <p className="mt-2 ml-9 text-sm text-gray-700 whitespace-pre-wrap dark:text-gray-300">
                    {comment.content}
                  </p>
                </div>
              ))
            )}
          </div>

          {/* Add comment form */}
          <div className="border-t border-gray-200 p-4 dark:border-gray-700">
            {commentError && (
              <p className="mb-2 text-xs text-red-600 dark:text-red-400">
                {commentError}
              </p>
            )}
            <div className="flex gap-2">
              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Add a comment..."
                className="flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white dark:placeholder:text-gray-500 dark:focus:border-blue-600"
                rows={2}
                maxLength={2000}
              />
              <button
                onClick={handleAddComment}
                disabled={!newComment.trim() || commentSubmitting}
                className="self-end rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-700 dark:hover:bg-blue-600"
              >
                {commentSubmitting ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
