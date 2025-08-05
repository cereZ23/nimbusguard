"use client";

import { useState } from "react";
import AppShell from "@/components/layout/app-shell";
import api from "@/lib/api";

type ExportFormat = "json" | "csv" | "pdf";

export default function ReportsPage() {
  const [severity, setSeverity] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [format, setFormat] = useState<ExportFormat>("json");
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setExportError(null);

    try {
      const res = await api.get("/export/findings", {
        params: {
          format,
          severity: severity !== "all" ? severity : undefined,
          status: status !== "all" ? status : undefined,
        },
        responseType: "blob",
      });

      const mimeType =
        format === "pdf"
          ? "application/pdf"
          : format === "csv"
            ? "text/csv"
            : "application/json";
      const ext = format === "pdf" ? "pdf" : format === "csv" ? "csv" : "json";
      const url = window.URL.createObjectURL(
        new Blob([res.data as BlobPart], { type: mimeType }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `findings-export.${ext}`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: Blob } };
      const status = axiosErr.response?.status;
      let message = "Export failed. Please try again.";
      if (status === 401 || status === 403) {
        message = "Authentication error. Please log in again.";
      } else if (status === 404) {
        message = "No findings match the selected filters.";
      } else if (status === 429) {
        message =
          "Too many export requests. Please wait a moment and try again.";
      } else if (axiosErr.response?.data instanceof Blob) {
        try {
          const text = await axiosErr.response.data.text();
          const parsed = JSON.parse(text);
          message = parsed.detail || parsed.error || message;
        } catch {
          // ignore parse errors
        }
      }
      setExportError(message);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Reports &amp; Export
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Export security findings in JSON, CSV, or PDF format with optional
            filters
          </p>
        </div>

        {/* Export card */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Export Findings
          </h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Select filters and format, then download the report
          </p>

          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-3">
            {/* Severity filter */}
            <div>
              <label
                htmlFor="severity-filter"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Severity
              </label>
              <select
                id="severity-filter"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="all">All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            {/* Status filter */}
            <div>
              <label
                htmlFor="status-filter"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Status
              </label>
              <select
                id="status-filter"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="all">All</option>
                <option value="pass">Pass</option>
                <option value="fail">Fail</option>
                <option value="error">Error</option>
                <option value="not_applicable">N/A</option>
              </select>
            </div>

            {/* Format toggle */}
            <div>
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Format
              </span>
              <div className="mt-1 inline-flex rounded-lg border border-gray-300 bg-gray-50 p-0.5 dark:border-gray-600 dark:bg-gray-900/50">
                <button
                  type="button"
                  onClick={() => setFormat("json")}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                    format === "json"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
                  }`}
                >
                  JSON
                </button>
                <button
                  type="button"
                  onClick={() => setFormat("csv")}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                    format === "csv"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
                  }`}
                >
                  CSV
                </button>
                <button
                  type="button"
                  onClick={() => setFormat("pdf")}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                    format === "pdf"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
                  }`}
                >
                  PDF
                </button>
              </div>
            </div>
          </div>

          {/* Error message */}
          {exportError && (
            <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {exportError}
            </div>
          )}

          {/* Export button */}
          <div className="mt-6">
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isExporting && (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              )}
              {isExporting ? "Exporting..." : "Export Findings"}
            </button>
          </div>
        </div>

        {/* Export history placeholder */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Export History
          </h2>
          <div className="mt-6 flex flex-col items-center justify-center py-12 text-gray-400 dark:text-gray-500">
            <p className="text-sm">Export history coming soon</p>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
