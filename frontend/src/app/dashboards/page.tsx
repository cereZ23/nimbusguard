"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import {
  LayoutDashboard,
  Plus,
  Trash2,
  Share2,
  Star,
  Clock,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type { CustomDashboard } from "@/types";

export default function DashboardsPage() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const {
    data: envelope,
    error,
    isLoading,
    mutate,
  } = useSWR("/custom-dashboards");

  const dashboards = (envelope?.data ?? []) as CustomDashboard[];

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      setCreating(true);
      const res = await api.post("/custom-dashboards", {
        name: newName.trim(),
        description: newDesc.trim() || null,
        layout: [],
        is_default: false,
        is_shared: false,
      });
      const created = res.data?.data as CustomDashboard;
      await mutate();
      setNewName("");
      setNewDesc("");
      if (created?.id) {
        router.push(`/dashboards/${created.id}`);
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this dashboard?")) return;
    await api.delete(`/custom-dashboards/${id}`);
    await mutate();
  };

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
              Custom Dashboards
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Create personalized dashboards with the widgets you need
            </p>
          </div>
        </div>

        {/* Create form */}
        <div className="rounded-2xl border border-gray-200/80 bg-white/70 p-6 shadow-lg backdrop-blur-sm dark:border-gray-700/60 dark:bg-gray-800/70">
          <h2 className="mb-4 text-lg font-bold text-gray-900 dark:text-white">
            Create New Dashboard
          </h2>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label
                htmlFor="dash-name"
                className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Name
              </label>
              <input
                id="dash-name"
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="My Dashboard"
                maxLength={100}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition-colors focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
              />
            </div>
            <div className="flex-1">
              <label
                htmlFor="dash-desc"
                className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Description (optional)
              </label>
              <input
                id="dash-desc"
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="A brief description..."
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 transition-colors focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
              />
            </div>
            <button
              type="button"
              onClick={handleCreate}
              disabled={creating || !newName.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
        </div>

        {/* Dashboard list */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-40 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-800"
              />
            ))}
          </div>
        ) : error ? (
          <ErrorState
            message={error?.message ?? "Failed to load dashboards"}
            onRetry={() => mutate()}
          />
        ) : dashboards.length === 0 ? (
          <div className="flex h-60 flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-gray-300 bg-white/50 dark:border-gray-700 dark:bg-gray-800/50">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 dark:bg-indigo-900/30">
              <LayoutDashboard className="h-8 w-8 text-indigo-400" />
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-600 dark:text-gray-300">
                No custom dashboards yet
              </p>
              <p className="mt-1 max-w-sm text-sm text-gray-400 dark:text-gray-500">
                Create your first custom dashboard using the form above.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {dashboards.map((dashboard) => (
              <button
                type="button"
                key={dashboard.id}
                onClick={() => router.push(`/dashboards/${dashboard.id}`)}
                className="group relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white/70 p-5 text-left shadow-lg backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl dark:border-gray-700/60 dark:bg-gray-800/70"
              >
                {/* Gradient accent */}
                <div className="absolute inset-x-0 top-0 h-1 rounded-t-2xl bg-gradient-to-r from-indigo-500 to-purple-500" />

                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate text-base font-bold text-gray-900 dark:text-white">
                        {dashboard.name}
                      </h3>
                      {dashboard.is_default && (
                        <Star className="h-3.5 w-3.5 shrink-0 fill-amber-400 text-amber-400" />
                      )}
                      {dashboard.is_shared && (
                        <Share2 className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
                      )}
                    </div>
                    {dashboard.description && (
                      <p className="mt-1 truncate text-sm text-gray-500 dark:text-gray-400">
                        {dashboard.description}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(dashboard.id);
                    }}
                    className="ml-2 rounded p-1.5 text-gray-300 opacity-0 transition-all hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 dark:text-gray-600 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                    title="Delete dashboard"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <div className="mt-4 flex items-center gap-3">
                  <span className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-300">
                    <LayoutDashboard className="h-3 w-3" />
                    {dashboard.layout.length} widget
                    {dashboard.layout.length !== 1 ? "s" : ""}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
                    <Clock className="h-3 w-3" />
                    {new Date(dashboard.created_at).toLocaleDateString()}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
