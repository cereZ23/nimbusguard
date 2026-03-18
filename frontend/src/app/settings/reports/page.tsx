"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  Calendar,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  FileText,
  Plus,
  Send,
  Trash2,
  X,
} from "lucide-react";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type { ReportHistoryEntry, ScheduledReport } from "@/types";

const REPORT_TYPE_LABELS: Record<string, string> = {
  executive_summary: "Executive Summary",
  compliance: "Compliance",
  technical_detail: "Technical Detail",
};
const SCHEDULE_LABELS: Record<string, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
};

export default function ReportsPage() {
  // -- SWR: scheduled reports --
  const {
    data: scheduledReportsEnvelope,
    error: scheduledReportsError,
    isLoading: scheduledReportsLoading,
    mutate: mutateScheduledReports,
  } = useSWR("/scheduled-reports");

  const scheduledReports = (scheduledReportsEnvelope?.data ??
    []) as ScheduledReport[];

  const error =
    scheduledReportsError?.message ?? scheduledReportsEnvelope?.error ?? null;

  const [actionError, setActionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // -- Report generation state --
  const [reportDownloading, setReportDownloading] = useState<string | null>(
    null,
  );
  const [reportError, setReportError] = useState<string | null>(null);
  const [complianceFramework, setComplianceFramework] = useState("cis_azure");

  const handleDownloadReport = async (
    endpoint: string,
    filename: string,
    params?: Record<string, string>,
  ) => {
    setReportDownloading(endpoint);
    setReportError(null);
    try {
      const queryString = params
        ? "?" + new URLSearchParams(params).toString()
        : "";
      const response = await api.get(`/reports/${endpoint}${queryString}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setReportError(
        axiosErr.response?.data?.detail ?? "Failed to generate report.",
      );
      setTimeout(() => setReportError(null), 5000);
    } finally {
      setReportDownloading(null);
    }
  };

  // -- Scheduled Reports state --
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    name: "",
    report_type: "executive_summary",
    schedule: "weekly",
    config_framework: "cis_azure",
    config_severity: "",
  });
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [reportHistory, setReportHistory] = useState<
    Record<string, ReportHistoryEntry[]>
  >({});
  const [historyLoading, setHistoryLoading] = useState<string | null>(null);

  const handleCreateScheduledReport = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      const config: Record<string, string> = {};
      if (scheduleForm.report_type === "compliance") {
        config.framework = scheduleForm.config_framework;
      }
      if (
        scheduleForm.report_type === "technical_detail" &&
        scheduleForm.config_severity
      ) {
        config.severity = scheduleForm.config_severity;
      }
      await api.post("/scheduled-reports", {
        name: scheduleForm.name,
        report_type: scheduleForm.report_type,
        schedule: scheduleForm.schedule,
        config,
      });
      setShowScheduleModal(false);
      setScheduleForm({
        name: "",
        report_type: "executive_summary",
        schedule: "weekly",
        config_framework: "cis_azure",
        config_severity: "",
      });
      mutateScheduledReports();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create scheduled report.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleScheduledReport = async (
    reportId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/scheduled-reports/${reportId}`, {
        is_active: !currentActive,
      });
      mutateScheduledReports();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to toggle scheduled report.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleDeleteScheduledReport = async (
    reportId: string,
    name: string,
  ) => {
    if (!window.confirm(`Delete scheduled report "${name}"?`)) return;
    setActionError(null);
    try {
      await api.delete(`/scheduled-reports/${reportId}`);
      mutateScheduledReports(
        (current: typeof scheduledReportsEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as ScheduledReport[]).filter(
              (r) => r.id !== reportId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to delete scheduled report.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleHistory = async (reportId: string) => {
    if (expandedReport === reportId) {
      setExpandedReport(null);
      return;
    }
    setExpandedReport(reportId);
    if (!reportHistory[reportId]) {
      setHistoryLoading(reportId);
      try {
        const res = await api.get(
          `/scheduled-reports/${reportId}/history?size=10`,
        );
        setReportHistory((prev) => ({
          ...prev,
          [reportId]: (res.data.data ?? []) as ReportHistoryEntry[],
        }));
      } catch {
        setReportHistory((prev) => ({
          ...prev,
          [reportId]: [],
        }));
      } finally {
        setHistoryLoading(null);
      }
    }
  };

  const handleDownloadHistoryReport = async (historyId: string) => {
    try {
      const response = await api.get(
        `/scheduled-reports/history/${historyId}/download`,
        { responseType: "blob" },
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `report-${historyId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setActionError("Failed to download report.");
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const formatFileSize = (bytes: number | null): string => {
    if (bytes === null || bytes === undefined) return "-";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // -- SIEM Export state --
  const [siemDownloading, setSiemDownloading] = useState<string | null>(null);
  const [siemError, setSiemError] = useState<string | null>(null);
  const [siemSeverity, setSiemSeverity] = useState("");
  const [siemStatus, setSiemStatus] = useState("");

  const handleSiemExport = async (format: "cef" | "leef" | "jsonl") => {
    setSiemDownloading(format);
    setSiemError(null);
    try {
      const params = new URLSearchParams();
      if (siemSeverity) params.set("severity", siemSeverity);
      if (siemStatus) params.set("status", siemStatus);
      const queryString = params.toString() ? `?${params.toString()}` : "";
      const response = await api.get(`/export/siem/${format}${queryString}`, {
        responseType: "blob",
      });
      const ext = format === "jsonl" ? "jsonl" : format;
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `findings-export.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setSiemError(
        axiosErr.response?.data?.detail ?? "Failed to export SIEM data.",
      );
      setTimeout(() => setSiemError(null), 5000);
    } finally {
      setSiemDownloading(null);
    }
  };

  return (
    <>
      {/* Error state for initial load */}
      {error && (
        <ErrorState message={error} onRetry={() => mutateScheduledReports()} />
      )}

      {/* Action error banner */}
      {actionError && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {actionError}
        </div>
      )}

      {/* Reports */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Reports
          </h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Generate and download PDF reports for your security posture
          </p>
        </div>

        <div className="space-y-0 divide-y divide-gray-100 dark:divide-gray-700">
          {reportError && (
            <div className="bg-red-50 px-6 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {reportError}
            </div>
          )}

          {/* Executive Summary */}
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <FileText
                size={16}
                className="text-blue-500 dark:text-blue-400"
              />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  Executive Summary
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  High-level security posture overview with KPIs and top failing
                  controls
                </p>
              </div>
            </div>
            <button
              onClick={() =>
                handleDownloadReport(
                  "executive-summary",
                  "executive-summary.pdf",
                )
              }
              disabled={reportDownloading === "executive-summary"}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              <Download
                size={14}
                className={
                  reportDownloading === "executive-summary"
                    ? "animate-pulse"
                    : ""
                }
              />
              {reportDownloading === "executive-summary"
                ? "Generating..."
                : "Download PDF"}
            </button>
          </div>

          {/* Compliance Report */}
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <FileText
                size={16}
                className="text-green-500 dark:text-green-400"
              />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  Compliance Report
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Framework compliance status with control-level detail and
                  remediation
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={complianceFramework}
                onChange={(e) => setComplianceFramework(e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
              >
                <option value="cis_azure">CIS Azure</option>
                <option value="soc2">SOC 2</option>
                <option value="nist">NIST CSF</option>
                <option value="iso27001">ISO 27001</option>
              </select>
              <button
                onClick={() =>
                  handleDownloadReport(
                    "compliance",
                    `compliance-${complianceFramework}.pdf`,
                    { framework: complianceFramework },
                  )
                }
                disabled={reportDownloading === "compliance"}
                className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
              >
                <Download
                  size={14}
                  className={
                    reportDownloading === "compliance" ? "animate-pulse" : ""
                  }
                />
                {reportDownloading === "compliance"
                  ? "Generating..."
                  : "Download PDF"}
              </button>
            </div>
          </div>

          {/* Technical Detail */}
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <FileText
                size={16}
                className="text-orange-500 dark:text-orange-400"
              />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  Technical Detail
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Detailed findings with evidence, asset inventory, and
                  remediation guidance
                </p>
              </div>
            </div>
            <button
              onClick={() =>
                handleDownloadReport("technical-detail", "technical-detail.pdf")
              }
              disabled={reportDownloading === "technical-detail"}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              <Download
                size={14}
                className={
                  reportDownloading === "technical-detail"
                    ? "animate-pulse"
                    : ""
                }
              />
              {reportDownloading === "technical-detail"
                ? "Generating..."
                : "Download PDF"}
            </button>
          </div>
        </div>
      </div>

      {/* Scheduled Reports */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Scheduled Reports
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Configure recurring PDF reports generated automatically
            </p>
          </div>
          <button
            onClick={() => setShowScheduleModal(true)}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            <Plus size={16} />
            Add Schedule
          </button>
        </div>

        {scheduledReportsLoading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {scheduledReports.map((sr) => (
              <div key={sr.id}>
                <div className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-4">
                    <div
                      className={`h-3 w-3 rounded-full ${
                        sr.is_active ? "bg-green-400" : "bg-gray-300"
                      }`}
                      title={sr.is_active ? "Active" : "Inactive"}
                    />
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {sr.name}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                        <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                          {REPORT_TYPE_LABELS[sr.report_type] ?? sr.report_type}
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                          <Clock size={10} />
                          {SCHEDULE_LABELS[sr.schedule] ?? sr.schedule}
                        </span>
                        {sr.config && Object.keys(sr.config).length > 0 && (
                          <span className="text-xs text-gray-400">
                            {Object.entries(sr.config)
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(", ")}
                          </span>
                        )}
                        {sr.last_run_at && (
                          <span className="text-xs">
                            Last: {new Date(sr.last_run_at).toLocaleString()}
                          </span>
                        )}
                        {sr.next_run_at && sr.is_active && (
                          <span className="text-xs">
                            Next: {new Date(sr.next_run_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggleHistory(sr.id)}
                      className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                      title="View history"
                    >
                      {expandedReport === sr.id ? (
                        <ChevronUp size={14} />
                      ) : (
                        <ChevronDown size={14} />
                      )}
                      History
                    </button>
                    <button
                      onClick={() =>
                        handleToggleScheduledReport(sr.id, sr.is_active)
                      }
                      className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                        sr.is_active
                          ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                          : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                      }`}
                      title={sr.is_active ? "Pause" : "Activate"}
                    >
                      <Check size={14} />
                      {sr.is_active ? "Pause" : "Activate"}
                    </button>
                    <button
                      onClick={() =>
                        handleDeleteScheduledReport(sr.id, sr.name)
                      }
                      className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                      title="Delete scheduled report"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {/* History panel */}
                {expandedReport === sr.id && (
                  <div className="border-t border-gray-100 bg-gray-50 px-6 py-3 dark:border-gray-700 dark:bg-gray-900/50">
                    {historyLoading === sr.id ? (
                      <div className="flex items-center justify-center py-4">
                        <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                      </div>
                    ) : (reportHistory[sr.id] ?? []).length === 0 ? (
                      <p className="py-3 text-center text-sm text-gray-500 dark:text-gray-400">
                        No reports generated yet.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-300">
                          Recent Reports
                        </p>
                        {(reportHistory[sr.id] ?? []).map((entry) => (
                          <div
                            key={entry.id}
                            className="flex items-center justify-between rounded-lg bg-white px-4 py-2 dark:bg-gray-800"
                          >
                            <div className="flex items-center gap-3">
                              <span
                                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                  entry.status === "completed"
                                    ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                                    : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                                }`}
                              >
                                {entry.status === "completed"
                                  ? "Completed"
                                  : "Failed"}
                              </span>
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {new Date(entry.generated_at).toLocaleString()}
                              </span>
                              {entry.file_size !== null && (
                                <span className="text-xs text-gray-400">
                                  {formatFileSize(entry.file_size)}
                                </span>
                              )}
                              {entry.error_message && (
                                <span className="max-w-xs truncate text-xs text-red-500">
                                  {entry.error_message}
                                </span>
                              )}
                            </div>
                            {entry.status === "completed" && (
                              <button
                                onClick={() =>
                                  handleDownloadHistoryReport(entry.id)
                                }
                                className="flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                              >
                                <Download size={12} />
                                Download
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {scheduledReports.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                <Calendar size={20} className="mb-2" />
                <p className="text-sm">No scheduled reports configured.</p>
                <p className="mt-1 text-sm">
                  Add a schedule to automate report generation.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* SIEM Export */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            SIEM Export
          </h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Export findings in SIEM-compatible formats for integration with your
            security operations platform
          </p>
        </div>

        <div className="space-y-0 divide-y divide-gray-100 dark:divide-gray-700">
          {siemError && (
            <div className="bg-red-50 px-6 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {siemError}
            </div>
          )}

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-4 px-6 py-4">
            <div className="flex items-center gap-2">
              <label
                htmlFor="siem_severity"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Severity
              </label>
              <select
                id="siem_severity"
                value={siemSeverity}
                onChange={(e) => setSiemSeverity(e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
              >
                <option value="">All severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label
                htmlFor="siem_status"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Status
              </label>
              <select
                id="siem_status"
                value={siemStatus}
                onChange={(e) => setSiemStatus(e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
              >
                <option value="">All statuses</option>
                <option value="fail">Fail</option>
                <option value="pass">Pass</option>
                <option value="error">Error</option>
              </select>
            </div>
          </div>

          {/* CEF Format */}
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <Send
                size={16}
                className="text-purple-500 dark:text-purple-400"
              />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  CEF Format
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Common Event Format -- Splunk, ArcSight, Microsoft Sentinel,
                  most SIEMs
                </p>
              </div>
            </div>
            <button
              onClick={() => handleSiemExport("cef")}
              disabled={siemDownloading === "cef"}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              <Download
                size={14}
                className={siemDownloading === "cef" ? "animate-pulse" : ""}
              />
              {siemDownloading === "cef" ? "Exporting..." : "Download"}
            </button>
          </div>

          {/* LEEF Format */}
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <Send
                size={16}
                className="text-orange-500 dark:text-orange-400"
              />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  LEEF Format
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Log Event Extended Format -- IBM QRadar
                </p>
              </div>
            </div>
            <button
              onClick={() => handleSiemExport("leef")}
              disabled={siemDownloading === "leef"}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              <Download
                size={14}
                className={siemDownloading === "leef" ? "animate-pulse" : ""}
              />
              {siemDownloading === "leef" ? "Exporting..." : "Download"}
            </button>
          </div>

          {/* JSON Lines Format */}
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <Send size={16} className="text-green-500 dark:text-green-400" />
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  JSON Lines
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Newline-delimited JSON -- Splunk HEC, Microsoft Sentinel,
                  Elastic
                </p>
              </div>
            </div>
            <button
              onClick={() => handleSiemExport("jsonl")}
              disabled={siemDownloading === "jsonl"}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              <Download
                size={14}
                className={siemDownloading === "jsonl" ? "animate-pulse" : ""}
              />
              {siemDownloading === "jsonl" ? "Exporting..." : "Download"}
            </button>
          </div>
        </div>
      </div>

      {/* Add Scheduled Report Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Add Scheduled Report
              </h2>
              <button
                onClick={() => {
                  setShowScheduleModal(false);
                  setFormError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateScheduledReport} className="space-y-4">
              <div>
                <label
                  htmlFor="sr_name"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Name
                </label>
                <input
                  id="sr_name"
                  type="text"
                  required
                  maxLength={100}
                  value={scheduleForm.name}
                  onChange={(e) =>
                    setScheduleForm((p) => ({ ...p, name: e.target.value }))
                  }
                  placeholder="Weekly Executive Summary"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label
                  htmlFor="sr_type"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Report Type
                </label>
                <select
                  id="sr_type"
                  value={scheduleForm.report_type}
                  onChange={(e) =>
                    setScheduleForm((p) => ({
                      ...p,
                      report_type: e.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="executive_summary">Executive Summary</option>
                  <option value="compliance">Compliance</option>
                  <option value="technical_detail">Technical Detail</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="sr_schedule"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Schedule
                </label>
                <select
                  id="sr_schedule"
                  value={scheduleForm.schedule}
                  onChange={(e) =>
                    setScheduleForm((p) => ({
                      ...p,
                      schedule: e.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="daily">Daily (midnight UTC)</option>
                  <option value="weekly">Weekly (Monday midnight UTC)</option>
                  <option value="monthly">Monthly (1st of month UTC)</option>
                </select>
              </div>

              {/* Conditional config options based on report type */}
              {scheduleForm.report_type === "compliance" && (
                <div>
                  <label
                    htmlFor="sr_framework"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Compliance Framework
                  </label>
                  <select
                    id="sr_framework"
                    value={scheduleForm.config_framework}
                    onChange={(e) =>
                      setScheduleForm((p) => ({
                        ...p,
                        config_framework: e.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  >
                    <option value="cis_azure">CIS Azure</option>
                    <option value="soc2">SOC 2</option>
                    <option value="nist">NIST CSF</option>
                    <option value="iso27001">ISO 27001</option>
                  </select>
                </div>
              )}

              {scheduleForm.report_type === "technical_detail" && (
                <div>
                  <label
                    htmlFor="sr_severity"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Severity Filter (optional)
                  </label>
                  <select
                    id="sr_severity"
                    value={scheduleForm.config_severity}
                    onChange={(e) =>
                      setScheduleForm((p) => ({
                        ...p,
                        config_severity: e.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  >
                    <option value="">All severities</option>
                    <option value="high">High only</option>
                    <option value="medium">Medium only</option>
                    <option value="low">Low only</option>
                  </select>
                </div>
              )}

              {formError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {formError}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowScheduleModal(false);
                    setFormError(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !scheduleForm.name.trim()}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Create Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
