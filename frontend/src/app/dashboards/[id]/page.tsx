"use client";

import { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import dynamic from "next/dynamic";
import {
  ArrowLeft,
  Pencil,
  Save,
  Plus,
  X,
  LayoutDashboard,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type {
  CustomDashboard,
  DashboardDataResponse,
  DashboardWidget,
} from "@/types";

import {
  SecureScoreWidget,
  FindingsCountWidget,
  ComplianceWidget,
  RecentFindingsWidget,
  TopControlsWidget,
  AssetsByTypeWidget,
} from "@/components/dashboard/widgets";

// Lazy load Recharts-heavy widgets
const SeverityBreakdownWidget = dynamic(
  () => import("@/components/dashboard/widgets/severity-breakdown-widget"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
    ),
  },
);

const TrendWidget = dynamic(
  () => import("@/components/dashboard/widgets/trend-widget"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[200px] animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
    ),
  },
);

// Available widget catalogue
const WIDGET_CATALOGUE: {
  type: string;
  label: string;
  description: string;
  defaultW: number;
  defaultH: number;
}[] = [
  {
    type: "secure_score",
    label: "Secure Score",
    description: "Current security score gauge",
    defaultW: 4,
    defaultH: 3,
  },
  {
    type: "findings_by_severity",
    label: "Severity Breakdown",
    description: "Donut chart of findings by severity",
    defaultW: 4,
    defaultH: 3,
  },
  {
    type: "total_assets",
    label: "Total Assets",
    description: "Asset count KPI",
    defaultW: 3,
    defaultH: 2,
  },
  {
    type: "total_findings",
    label: "Total Findings",
    description: "Finding count KPI",
    defaultW: 3,
    defaultH: 2,
  },
  {
    type: "top_failing_controls",
    label: "Top Failing Controls",
    description: "Controls with most failures",
    defaultW: 6,
    defaultH: 4,
  },
  {
    type: "recent_findings",
    label: "Recent Findings",
    description: "Latest security findings list",
    defaultW: 6,
    defaultH: 4,
  },
  {
    type: "compliance_score",
    label: "Compliance Score",
    description: "Overall compliance percentage",
    defaultW: 4,
    defaultH: 3,
  },
  {
    type: "findings_trend",
    label: "Findings Trend",
    description: "Line chart of findings over time",
    defaultW: 8,
    defaultH: 3,
  },
  {
    type: "assets_by_type",
    label: "Assets by Type",
    description: "Breakdown of asset types",
    defaultW: 4,
    defaultH: 4,
  },
];

export default function CustomDashboardDetailPage() {
  const params = useParams();
  const router = useRouter();
  const dashboardId = params.id as string;

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [localLayout, setLocalLayout] = useState<DashboardWidget[] | null>(
    null,
  );
  const [showAddPanel, setShowAddPanel] = useState(false);

  // Fetch dashboard metadata
  const {
    data: dashEnvelope,
    error: dashError,
    isLoading: dashLoading,
    mutate: mutateDash,
  } = useSWR(`/custom-dashboards`);

  // Fetch widget data
  const {
    data: dataEnvelope,
    error: dataError,
    isLoading: dataLoading,
    mutate: mutateData,
  } = useSWR(`/custom-dashboards/${dashboardId}/data`);

  const dashboards = (dashEnvelope?.data ?? []) as CustomDashboard[];
  const dashboard = dashboards.find((d) => d.id === dashboardId) ?? null;
  const widgetDataResponse = (dataEnvelope?.data ??
    null) as DashboardDataResponse | null;

  const activeLayout = localLayout ?? dashboard?.layout ?? [];

  // Build a map of widget type -> data for quick lookup
  const widgetDataMap = new Map<string, unknown>();
  if (widgetDataResponse?.widgets) {
    for (const wd of widgetDataResponse.widgets) {
      widgetDataMap.set(wd.widget, wd.data);
    }
  }

  const handleStartEdit = () => {
    setLocalLayout([...(dashboard?.layout ?? [])]);
    setEditing(true);
  };

  const handleCancelEdit = () => {
    setLocalLayout(null);
    setEditing(false);
    setShowAddPanel(false);
  };

  const handleSave = async () => {
    if (!localLayout) return;
    try {
      setSaving(true);
      await api.put(`/custom-dashboards/${dashboardId}`, {
        layout: localLayout,
      });
      await mutateDash();
      await mutateData();
      setLocalLayout(null);
      setEditing(false);
      setShowAddPanel(false);
    } finally {
      setSaving(false);
    }
  };

  const handleAddWidget = (widgetType: string) => {
    const catalogue = WIDGET_CATALOGUE.find((w) => w.type === widgetType);
    if (!catalogue || !localLayout) return;

    // Calculate next y position
    let maxY = 0;
    for (const w of localLayout) {
      const bottom = w.y + w.h;
      if (bottom > maxY) maxY = bottom;
    }

    const newWidget: DashboardWidget = {
      widget: widgetType,
      x: 0,
      y: maxY,
      w: catalogue.defaultW,
      h: catalogue.defaultH,
      config: {},
    };
    setLocalLayout([...localLayout, newWidget]);
    setShowAddPanel(false);
  };

  const handleRemoveWidget = useCallback(
    (index: number) => {
      if (!localLayout) return;
      const updated = localLayout.filter((_, i) => i !== index);
      setLocalLayout(updated);
    },
    [localLayout],
  );

  const handleResizeWidget = useCallback(
    (index: number, larger: boolean) => {
      if (!localLayout) return;
      const updated = [...localLayout];
      const widget = { ...updated[index] };
      if (larger) {
        widget.w = Math.min(widget.w + 2, 12);
      } else {
        widget.w = Math.max(widget.w - 2, 2);
      }
      updated[index] = widget;
      setLocalLayout(updated);
    },
    [localLayout],
  );

  const isLoading = dashLoading || dataLoading;
  const error = dashError ?? dataError;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.push("/dashboards")}
              className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-gray-900 dark:text-white">
                {dashboard?.name ?? "Dashboard"}
              </h1>
              {dashboard?.description && (
                <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                  {dashboard.description}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {editing ? (
              <>
                <button
                  type="button"
                  onClick={() => setShowAddPanel(!showAddPanel)}
                  className="inline-flex items-center gap-2 rounded-lg border border-indigo-300 px-3 py-2 text-sm font-medium text-indigo-600 transition-colors hover:bg-indigo-50 dark:border-indigo-700 dark:text-indigo-400 dark:hover:bg-indigo-900/30"
                >
                  <Plus className="h-4 w-4" />
                  Add Widget
                </button>
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  <X className="h-4 w-4" />
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Save className="h-4 w-4" />
                  {saving ? "Saving..." : "Save Layout"}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={handleStartEdit}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                <Pencil className="h-4 w-4" />
                Edit Layout
              </button>
            )}
          </div>
        </div>

        {/* Add widget panel */}
        {showAddPanel && (
          <div className="rounded-2xl border border-indigo-200 bg-indigo-50/50 p-4 dark:border-indigo-800 dark:bg-indigo-900/20">
            <h3 className="mb-3 text-sm font-bold text-indigo-700 dark:text-indigo-300">
              Available Widgets
            </h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {WIDGET_CATALOGUE.map((w) => (
                <button
                  type="button"
                  key={w.type}
                  onClick={() => handleAddWidget(w.type)}
                  className="flex items-start gap-3 rounded-lg border border-indigo-200 bg-white p-3 text-left transition-all hover:border-indigo-400 hover:shadow-sm dark:border-indigo-700 dark:bg-gray-800 dark:hover:border-indigo-500"
                >
                  <LayoutDashboard className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      {w.label}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {w.description}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Loading */}
        {isLoading ? (
          <div className="grid grid-cols-12 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="col-span-6 h-48 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800"
              />
            ))}
          </div>
        ) : error ? (
          <ErrorState
            message={error?.message ?? "Failed to load dashboard data"}
            onRetry={() => {
              mutateDash();
              mutateData();
            }}
          />
        ) : activeLayout.length === 0 ? (
          <div className="flex h-60 flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-gray-300 bg-white/50 dark:border-gray-700 dark:bg-gray-800/50">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 dark:bg-indigo-900/30">
              <LayoutDashboard className="h-8 w-8 text-indigo-400" />
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-600 dark:text-gray-300">
                Empty dashboard
              </p>
              <p className="mt-1 max-w-sm text-sm text-gray-400 dark:text-gray-500">
                Click &quot;Edit Layout&quot; and add widgets to customize this
                dashboard.
              </p>
            </div>
          </div>
        ) : (
          /* Widget grid */
          <div className="grid grid-cols-12 gap-4">
            {activeLayout.map((widget, index) => (
              <WidgetRenderer
                key={`${widget.widget}-${index}`}
                widget={widget}
                data={widgetDataMap.get(widget.widget)}
                editing={editing}
                onRemove={() => handleRemoveWidget(index)}
                onResize={(larger) => handleResizeWidget(index, larger)}
              />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Widget renderer -- maps widget type string to component
// ---------------------------------------------------------------------------

interface WidgetRendererProps {
  widget: DashboardWidget;
  data: unknown;
  editing: boolean;
  onRemove: () => void;
  onResize: (larger: boolean) => void;
}

function WidgetRenderer({
  widget,
  data,
  editing,
  onRemove,
  onResize,
}: WidgetRendererProps) {
  const commonProps = {
    colSpan: widget.w,
    rowSpan: widget.h,
    editing,
    onRemove,
    onResize,
  };

  switch (widget.widget) {
    case "secure_score":
      return (
        <SecureScoreWidget
          data={data as { score: number | null } | null}
          {...commonProps}
        />
      );
    case "findings_by_severity":
      return (
        <SeverityBreakdownWidget
          data={data as Record<string, number> | null}
          {...commonProps}
        />
      );
    case "total_assets":
      return (
        <FindingsCountWidget
          widgetType="total_assets"
          data={data as { count: number } | null}
          {...commonProps}
        />
      );
    case "total_findings":
      return (
        <FindingsCountWidget
          widgetType="total_findings"
          data={data as { count: number } | null}
          {...commonProps}
        />
      );
    case "top_failing_controls":
      return (
        <TopControlsWidget
          data={
            data as
              | {
                  code: string;
                  name: string;
                  severity: string;
                  fail_count: number;
                  total_count: number;
                }[]
              | null
          }
          {...commonProps}
        />
      );
    case "recent_findings":
      return (
        <RecentFindingsWidget
          data={
            data as
              | {
                  id: string;
                  title: string;
                  severity: string;
                  status: string;
                  first_detected_at: string | null;
                }[]
              | null
          }
          {...commonProps}
        />
      );
    case "compliance_score":
      return (
        <ComplianceWidget
          data={
            data as {
              score: number;
              total: number;
              passing: number;
            } | null
          }
          {...commonProps}
        />
      );
    case "findings_trend":
      return (
        <TrendWidget
          data={
            data as
              | { date: string; high: number; medium: number; low: number }[]
              | null
          }
          {...commonProps}
        />
      );
    case "assets_by_type":
      return (
        <AssetsByTypeWidget
          data={data as Record<string, number> | null}
          {...commonProps}
        />
      );
    default:
      return (
        <div
          className="flex items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800"
          style={{
            gridColumn: `span ${widget.w}`,
            gridRow: `span ${widget.h}`,
          }}
        >
          <p className="text-sm text-gray-400">
            Unknown widget: {widget.widget}
          </p>
        </div>
      );
  }
}
