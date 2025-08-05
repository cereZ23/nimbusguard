"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Server,
  MapPin,
  Calendar,
  Tag,
  ExternalLink,
  Network,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import SeverityBadge from "@/components/ui/severity-badge";
import StatusBadge from "@/components/ui/status-badge";
import ErrorState from "@/components/ui/error-state";
import { AssetDetailSkeleton } from "@/components/ui/skeleton";
import api from "@/lib/api";
import type { Asset, AssetRelationship, Finding } from "@/types";

export default function AssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [asset, setAsset] = useState<Asset | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [relationships, setRelationships] = useState<AssetRelationship[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAssetDetail = () => {
    if (!id) return;
    setError(null);
    setIsLoading(true);

    Promise.all([
      api.get(`/assets/${id}`),
      api.get("/findings", { params: { asset_id: id, size: 100 } }),
      api
        .get(`/assets/${id}/relationships`)
        .catch(() => ({ data: { data: [] } })),
    ])
      .then(([assetRes, findingsRes, relRes]) => {
        setAsset(assetRes.data?.data as Asset);
        setFindings((findingsRes.data?.data as Finding[]) ?? []);
        setRelationships((relRes.data?.data as AssetRelationship[]) ?? []);
      })
      .catch((err) => {
        setError(err?.response?.data?.error ?? "Failed to load asset");
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchAssetDetail();
  }, [id]);

  const formatResourceType = (type: string) =>
    type
      .split("/")
      .pop()
      ?.replace(/([A-Z])/g, " $1")
      .trim() ?? type;

  if (isLoading) {
    return (
      <AppShell>
        <AssetDetailSkeleton />
      </AppShell>
    );
  }

  if (error || !asset) {
    return (
      <AppShell>
        <ErrorState
          message={error ?? "Asset not found"}
          onRetry={error ? fetchAssetDetail : undefined}
        />
        <div className="mt-2 text-center">
          <button
            onClick={() => router.push("/assets")}
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            Back to Assets
          </button>
        </div>
      </AppShell>
    );
  }

  const failCount = findings.filter((f) => f.status === "fail").length;
  const passCount = findings.filter((f) => f.status === "pass").length;

  const azurePortalUrl = asset.provider_id
    ? `https://portal.azure.com/#@/resource${asset.provider_id}`
    : null;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Back + header */}
        <div>
          <button
            onClick={() => router.push("/assets")}
            className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Assets
          </button>

          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                {asset.name}
              </h1>
              <p className="mt-1 text-sm text-gray-500 font-mono dark:text-gray-400">
                {asset.provider_id}
              </p>
              {azurePortalUrl && (
                <a
                  href={azurePortalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-600 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-blue-600 dark:hover:text-blue-400"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Open in Azure Portal
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Info cards */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:bg-gray-800 dark:border-gray-700">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Server className="h-4 w-4" />
              Type
            </div>
            <p className="mt-1 font-medium text-gray-900 dark:text-white">
              {formatResourceType(asset.resource_type)}
            </p>
            <p className="text-xs text-gray-400 font-mono dark:text-gray-500">
              {asset.resource_type}
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:bg-gray-800 dark:border-gray-700">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <MapPin className="h-4 w-4" />
              Region
            </div>
            <p className="mt-1 font-medium text-gray-900 dark:text-white">
              {asset.region ?? "—"}
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:bg-gray-800 dark:border-gray-700">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Calendar className="h-4 w-4" />
              First Seen
            </div>
            <p className="mt-1 font-medium text-gray-900 dark:text-white">
              {new Date(asset.first_seen_at).toLocaleDateString()}
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:bg-gray-800 dark:border-gray-700">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Calendar className="h-4 w-4" />
              Last Seen
            </div>
            <p className="mt-1 font-medium text-gray-900 dark:text-white">
              {new Date(asset.last_seen_at).toLocaleDateString()}
            </p>
          </div>
        </div>

        {/* Tags */}
        {asset.tags && Object.keys(asset.tags).length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:bg-gray-800 dark:border-gray-700">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              <Tag className="h-4 w-4" />
              Tags
            </h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(asset.tags).map(([key, value]) => (
                <span
                  key={key}
                  className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                >
                  <span className="font-medium">{key}</span>: {value}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Security posture summary */}
        <div className="flex gap-4">
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm flex-1 text-center dark:bg-gray-800 dark:border-gray-700">
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {findings.length}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Total Findings
            </p>
          </div>
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 shadow-sm flex-1 text-center dark:bg-red-900/20 dark:border-red-800">
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
              {failCount}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Failing</p>
          </div>
          <div className="rounded-xl border border-green-200 bg-green-50 p-4 shadow-sm flex-1 text-center dark:bg-green-900/20 dark:border-green-800">
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {passCount}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Passing</p>
          </div>
        </div>

        {/* Related Assets */}
        {relationships.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:bg-gray-800 dark:border-gray-700">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:bg-gray-900/50 dark:border-gray-700">
              <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Network className="h-4 w-4" />
                Related Assets ({relationships.length})
              </h2>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {relationships.map((rel) => (
                <div
                  key={rel.id}
                  onClick={() => router.push(`/assets/${rel.related_asset.id}`)}
                  className="flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50"
                >
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      rel.direction === "outgoing"
                        ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                        : "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                    }`}
                  >
                    {rel.relationship_type}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                      {rel.related_asset.name}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      {rel.related_asset.resource_type}
                    </p>
                  </div>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400">
                    {rel.related_asset.provider}
                  </span>
                  <ArrowRight className="h-4 w-4 text-gray-400" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Findings table */}
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:bg-gray-800 dark:border-gray-700">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:bg-gray-900/50 dark:border-gray-700">
            <h2 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Findings for this Asset ({findings.length})
            </h2>
          </div>
          {findings.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
              No findings for this asset
            </div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 dark:bg-gray-900/50 dark:border-gray-700">
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Title
                  </th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Severity
                  </th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </th>
                  <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Last Evaluated
                  </th>
                </tr>
              </thead>
              <tbody>
                {findings.map((f) => (
                  <tr
                    key={f.id}
                    onClick={() => router.push(`/findings/${f.id}`)}
                    className="cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                      {f.title}
                    </td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={f.severity} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={f.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {new Date(f.last_evaluated_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
