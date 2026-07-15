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
  UserPlus,
  MessageSquare,
  Trash2,
  Send,
  History,
  Layers,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import PriorityBadge from "@/components/ui/priority-badge";
import SeverityBadge from "@/components/ui/severity-badge";
import StatusBadge from "@/components/ui/status-badge";
import ErrorState from "@/components/ui/error-state";
import RemediationPanel from "@/components/findings/remediation-panel";
import type { RemediationData } from "@/components/findings/remediation-panel";
import TimelineItem from "@/components/findings/timeline-item";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { extractApiError } from "@/lib/errors";
import { formatDate, formatDateTime } from "@/lib/dates";
import { PROVIDERS, providerFromResourceType } from "@/config/providers";
import type {
  FindingComment,
  FindingEvent,
  Priority,
  SimilarFinding,
  TenantUser,
} from "@/types";

interface FindingDetailData {
  id: string;
  status: string;
  severity: string;
  priority: string | null;
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
    effort?: string | null;
    exposure?: string | null;
  } | null;
  evidences: Array<{
    id: string;
    snapshot: Record<string, unknown>;
    collected_at: string;
  }>;
  total_evidence_count: number;
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

  // Timeline state (cursor-paginated, newest first)
  const [timelineEvents, setTimelineEvents] = useState<FindingEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineTotal, setTimelineTotal] = useState(0);
  const [timelineHasMore, setTimelineHasMore] = useState(false);
  const [timelineCursor, setTimelineCursor] = useState<string | null>(null);

  // Comments state (cursor-paginated, newest first from API, reversed for UI)
  const [commentsTotal, setCommentsTotal] = useState(0);
  const [commentsHasMore, setCommentsHasMore] = useState(false);
  const [commentsCursor, setCommentsCursor] = useState<string | null>(null);

  // Evidence history state (lazy — older rows are loaded on demand)
  const [olderEvidence, setOlderEvidence] = useState<
    Array<{
      id: string;
      snapshot: Record<string, unknown>;
      collected_at: string;
    }>
  >([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceHasMore, setEvidenceHasMore] = useState(false);
  const [evidenceCursor, setEvidenceCursor] = useState<string | null>(null);

  // Similar findings state
  const [similarFindings, setSimilarFindings] = useState<SimilarFinding[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);

  // Remediation snippets state
  const [remediation, setRemediation] = useState<RemediationData | null>(null);

  // Meta shape returned by cursor-paginated endpoints.
  interface CursorMeta {
    total: number;
    limit: number;
    has_more: boolean;
    next_cursor: string | null;
  }

  const isAdmin = user?.role === "admin";

  const fetchFindingDetail = useCallback(() => {
    if (!id) return;
    setError(null);
    setIsLoading(true);

    api
      .get(`/findings/${id}`)
      .then((res) => {
        const detail = res.data?.data as FindingDetailData;
        setFinding(detail);
        // Reset the "older evidence" state whenever the finding is
        // refreshed so we don't mix old and new history.
        setOlderEvidence([]);
        setEvidenceCursor(detail?.evidences?.[0]?.collected_at ?? null);
        // "Has more" for evidence is derived from the total count vs
        // the single embedded evidence row.
        setEvidenceHasMore((detail?.total_evidence_count ?? 0) > 1);
      })
      .catch((err: unknown) => {
        setError(extractApiError(err));
      })
      .finally(() => setIsLoading(false));
  }, [id]);

  const fetchComments = useCallback(
    (append = false, before?: string) => {
      if (!id) return;
      if (!append) setCommentsLoading(true);

      const params = new URLSearchParams({ limit: "20" });
      if (before) params.set("before", before);

      api
        .get(`/findings/${id}/comments?${params.toString()}`)
        .then((res) => {
          const page = (res.data?.data as FindingComment[]) ?? [];
          // API returns newest first; we render chronologically (oldest
          // at top) so we reverse the page and prepend older pages.
          const reversedPage = [...page].reverse();
          setComments((prev) =>
            append ? [...reversedPage, ...prev] : reversedPage,
          );
          const meta = res.data?.meta as CursorMeta | undefined;
          if (meta) {
            setCommentsTotal(meta.total);
            setCommentsHasMore(meta.has_more);
            setCommentsCursor(meta.next_cursor);
          }
        })
        .catch(() => {
          // Silently fail for comments — not critical
        })
        .finally(() => setCommentsLoading(false));
    },
    [id],
  );

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

  const fetchTimeline = useCallback(
    (append = false, before?: string) => {
      if (!id) return;
      if (!append) setTimelineLoading(true);

      const params = new URLSearchParams({ limit: "20" });
      if (before) params.set("before", before);

      api
        .get(`/findings/${id}/timeline?${params.toString()}`)
        .then((res) => {
          const page = (res.data?.data as FindingEvent[]) ?? [];
          // Timeline is rendered newest-first so we append older pages
          // at the bottom (after the existing events).
          setTimelineEvents((prev) => (append ? [...prev, ...page] : page));
          const meta = res.data?.meta as CursorMeta | undefined;
          if (meta) {
            setTimelineTotal(meta.total);
            setTimelineHasMore(meta.has_more);
            setTimelineCursor(meta.next_cursor);
          }
        })
        .catch(() => {
          // Silently fail for timeline — not critical
        })
        .finally(() => setTimelineLoading(false));
    },
    [id],
  );

  const fetchOlderEvidence = useCallback(
    (before?: string) => {
      if (!id) return;
      setEvidenceLoading(true);

      const params = new URLSearchParams({ limit: "20" });
      if (before) params.set("before", before);

      api
        .get(`/findings/${id}/evidence?${params.toString()}`)
        .then((res) => {
          const page =
            (res.data?.data as Array<{
              id: string;
              snapshot: Record<string, unknown>;
              collected_at: string;
            }>) ?? [];
          // The finding detail already embeds the single most recent
          // evidence row — every /evidence page contains older rows so
          // we append to the existing list.
          setOlderEvidence((prev) => [...prev, ...page]);
          const meta = res.data?.meta as CursorMeta | undefined;
          if (meta) {
            setEvidenceHasMore(meta.has_more);
            setEvidenceCursor(meta.next_cursor);
          }
        })
        .catch(() => {
          // Silently fail — evidence history is optional context.
        })
        .finally(() => setEvidenceLoading(false));
    },
    [id],
  );

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
      setWaiverError(extractApiError(err));
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
      setAssignError(extractApiError(err));
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
      setCommentError(extractApiError(err));
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
      setCommentError(extractApiError(err));
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

  const providerConfig =
    PROVIDERS[providerFromResourceType(finding.asset?.resource_type)];
  const portalUrl = finding.asset
    ? providerConfig.portalUrlForAsset(finding.asset)
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
                <PriorityBadge
                  value={finding.priority as Priority | null}
                  severity={finding.severity}
                  effort={finding.control?.effort}
                  exposure={finding.control?.exposure}
                />
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
              className="w-full rounded-lg border border-purple-200 bg-white px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:border-purple-700 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500 dark:focus:border-purple-600"
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
              {formatDate(finding.first_detected_at)}
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Clock className="h-4 w-4" />
              Last Evaluated
            </div>
            <p className="mt-1 font-medium text-gray-900 dark:text-white">
              {formatDate(finding.last_evaluated_at)}
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
              {portalUrl && (
                <a
                  href={portalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="mt-2 inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-600 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:border-blue-600 dark:hover:text-blue-400"
                >
                  <ExternalLink className="h-3 w-3" />
                  Open in {providerConfig.portalName}
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

        {/* Evidence — latest row embedded in detail, older rows lazy-loaded */}
        {(finding.evidences.length > 0 || finding.total_evidence_count > 0) && (
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50">
              <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
                <FileText className="h-4 w-4" />
                Evidence ({finding.total_evidence_count})
              </h2>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {finding.evidences.map((ev) => (
                <div key={ev.id} className="p-4">
                  <p className="mb-2 text-xs text-gray-400 dark:text-gray-500">
                    Latest · Collected: {formatDateTime(ev.collected_at)}
                  </p>
                  <pre className="max-h-64 overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                    {JSON.stringify(ev.snapshot, null, 2)}
                  </pre>
                </div>
              ))}
              {olderEvidence.map((ev) => (
                <div key={ev.id} className="p-4">
                  <p className="mb-2 text-xs text-gray-400 dark:text-gray-500">
                    Collected: {formatDateTime(ev.collected_at)}
                  </p>
                  <pre className="max-h-64 overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                    {JSON.stringify(ev.snapshot, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
            {evidenceHasMore && (
              <div className="border-t border-gray-100 p-3 text-center dark:border-gray-700">
                <button
                  onClick={() =>
                    fetchOlderEvidence(evidenceCursor ?? undefined)
                  }
                  disabled={evidenceLoading}
                  className="text-xs font-medium text-blue-600 hover:underline disabled:opacity-50 dark:text-blue-400"
                >
                  {evidenceLoading
                    ? "Loading…"
                    : `Load older evidence (${
                        finding.total_evidence_count -
                        finding.evidences.length -
                        olderEvidence.length
                      } remaining)`}
                </button>
              </div>
            )}
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
              Timeline ({timelineTotal || timelineEvents.length})
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
              <>
                <div className="relative">
                  {/* Vertical line */}
                  <div className="absolute left-[15px] top-2 bottom-2 w-px bg-gray-200 dark:bg-gray-700" />

                  <div className="space-y-4">
                    {timelineEvents.map((event) => (
                      <TimelineItem key={event.id} event={event} />
                    ))}
                  </div>
                </div>
                {timelineHasMore && (
                  <div className="mt-4 text-center">
                    <button
                      onClick={() =>
                        fetchTimeline(true, timelineCursor ?? undefined)
                      }
                      disabled={timelineLoading}
                      className="text-xs font-medium text-blue-600 hover:underline disabled:opacity-50 dark:text-blue-400"
                    >
                      {timelineLoading
                        ? "Loading…"
                        : `Load older events (${
                            timelineTotal - timelineEvents.length
                          } remaining)`}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Comments section */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/50">
            <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
              <MessageSquare className="h-4 w-4" />
              Comments ({commentsTotal || comments.length})
            </h2>
          </div>

          {commentsHasMore && (
            <div className="border-b border-gray-100 p-3 text-center dark:border-gray-700">
              <button
                onClick={() => fetchComments(true, commentsCursor ?? undefined)}
                disabled={commentsLoading}
                className="text-xs font-medium text-blue-600 hover:underline disabled:opacity-50 dark:text-blue-400"
              >
                {commentsLoading
                  ? "Loading…"
                  : `Load older comments (${
                      commentsTotal - comments.length
                    } remaining)`}
              </button>
            </div>
          )}

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
                          {formatDateTime(comment.created_at)}
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
                className="flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder:text-gray-500 dark:focus:border-blue-600"
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
