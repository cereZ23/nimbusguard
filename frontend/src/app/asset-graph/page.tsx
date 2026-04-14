"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Filter,
  LayoutGrid,
  Network,
  RefreshCw,
  Search,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type { AssetGraph, GraphEdge, GraphNode } from "@/types";

// ── Constants ───────────────────────────────────────────────────────

const PROVIDER_COLORS: Record<string, string> = {
  azure: "#0078D4",
  aws: "#FF9900",
};

const PROVIDER_BG: Record<string, string> = {
  azure: "bg-blue-100 dark:bg-blue-900/30",
  aws: "bg-orange-100 dark:bg-orange-900/30",
};

const SEVERITY_COLORS: Record<string, string> = {
  high: "text-red-600 dark:text-red-400",
  medium: "text-amber-600 dark:text-amber-400",
  low: "text-blue-600 dark:text-blue-400",
};

const SEVERITY_DOT: Record<string, string> = {
  high: "bg-red-500",
  medium: "bg-amber-500",
  low: "bg-blue-500",
};

const RELATIONSHIP_LABELS: Record<string, string> = {
  contains: "Contains",
  uses: "Uses",
  attached_to: "Attached To",
  routes_to: "Routes To",
  protects: "Protects",
  member_of: "Member Of",
};

const RELATIONSHIP_COLORS: Record<string, string> = {
  contains: "#6366f1",
  uses: "#3b82f6",
  attached_to: "#10b981",
  routes_to: "#f59e0b",
  protects: "#ef4444",
  member_of: "#8b5cf6",
};

// ── Helper: format resource type ────────────────────────────────────

function formatResourceType(type: string): string {
  const last = type.split("/").pop() ?? type;
  return last.replace(/([A-Z])/g, " $1").trim();
}

function shortResourceType(type: string): string {
  const parts = type.split("/");
  return parts[parts.length - 1] ?? type;
}

// ── Component ───────────────────────────────────────────────────────

type ViewMode = "list" | "graph";

export default function AssetGraphPage() {
  const router = useRouter();
  const [graph, setGraph] = useState<AssetGraph | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [search, setSearch] = useState("");
  const [providerFilter, setProviderFilter] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const fetchGraph = useCallback(() => {
    setError(null);
    setIsLoading(true);

    const params: Record<string, string> = {};
    if (providerFilter) {
      params.provider = providerFilter;
    }

    api
      .get("/assets/graph", { params })
      .then((res) => {
        setGraph(res.data?.data as AssetGraph);
      })
      .catch((err) => {
        setError(err?.response?.data?.error ?? "Failed to load asset graph");
      })
      .finally(() => setIsLoading(false));
  }, [providerFilter]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Filter nodes by search
  const filteredNodes = useMemo(() => {
    if (!graph) return [];
    if (!search) return graph.nodes;
    const lower = search.toLowerCase();
    return graph.nodes.filter(
      (n) =>
        n.label.toLowerCase().includes(lower) ||
        n.resource_type.toLowerCase().includes(lower) ||
        (n.region ?? "").toLowerCase().includes(lower),
    );
  }, [graph, search]);

  // Group filtered nodes by resource type
  const groupedNodes = useMemo(() => {
    const groups: Record<string, GraphNode[]> = {};
    for (const node of filteredNodes) {
      const key = node.resource_type;
      if (!groups[key]) groups[key] = [];
      groups[key].push(node);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredNodes]);

  // Get edges connected to selected node
  const selectedEdges = useMemo(() => {
    if (!selectedNode || !graph) return [];
    return graph.edges.filter(
      (e) => e.source === selectedNode.id || e.target === selectedNode.id,
    );
  }, [selectedNode, graph]);

  // Get connected nodes for selected node
  const connectedNodes = useMemo(() => {
    if (!selectedNode || !graph) return [];
    const connectedIds = new Set<string>();
    for (const edge of selectedEdges) {
      if (edge.source === selectedNode.id) connectedIds.add(edge.target);
      if (edge.target === selectedNode.id) connectedIds.add(edge.source);
    }
    return graph.nodes.filter((n) => connectedIds.has(n.id));
  }, [selectedNode, selectedEdges, graph]);

  // Available providers from graph data
  const providers = useMemo(() => {
    if (!graph) return [];
    return Object.keys(graph.stats.nodes_by_provider);
  }, [graph]);

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="h-8 w-48 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-24 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-700"
              />
            ))}
          </div>
          <div className="h-96 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-700" />
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <ErrorState message={error} onRetry={fetchGraph} />
      </AppShell>
    );
  }

  if (!graph) return null;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Asset Graph
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Cross-cloud resource relationship visualization
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchGraph}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Total Nodes
            </p>
            <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
              {graph.stats.total_nodes}
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Total Edges
            </p>
            <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
              {graph.stats.total_edges}
            </p>
          </div>
          {Object.entries(graph.stats.nodes_by_provider).map(
            ([prov, count]) => (
              <div
                key={prov}
                className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {prov.charAt(0).toUpperCase() + prov.slice(1)} Assets
                </p>
                <p
                  className="mt-1 text-2xl font-bold"
                  style={{ color: PROVIDER_COLORS[prov] ?? "#6b7280" }}
                >
                  {count}
                </p>
              </div>
            ),
          )}
        </div>

        {/* Relationship type breakdown */}
        {Object.keys(graph.stats.edges_by_type).length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
              Relationship Types
            </h3>
            <div className="flex flex-wrap gap-3">
              {Object.entries(graph.stats.edges_by_type).map(
                ([type, count]) => (
                  <span
                    key={type}
                    className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300"
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{
                        backgroundColor: RELATIONSHIP_COLORS[type] ?? "#6b7280",
                      }}
                    />
                    {RELATIONSHIP_LABELS[type] ?? type}
                    <span className="text-gray-400 dark:text-gray-500">
                      {count}
                    </span>
                  </span>
                ),
              )}
            </div>
          </div>
        )}

        {/* Toolbar: search + filters + view toggle */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-1 items-center gap-3">
            <div className="relative flex-1 sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search assets..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-9 pr-4 text-sm text-gray-900 placeholder-gray-400 transition-colors focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-500"
              />
            </div>
            {providers.length > 1 && (
              <div className="flex items-center gap-1.5">
                <Filter className="h-4 w-4 text-gray-400" />
                <select
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                  className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
                >
                  <option value="">All Providers</option>
                  {providers.map((p) => (
                    <option key={p} value={p}>
                      {p.charAt(0).toUpperCase() + p.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div className="flex items-center rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-600 dark:bg-gray-800">
            <button
              onClick={() => setViewMode("list")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                viewMode === "list"
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              List
            </button>
            <button
              onClick={() => setViewMode("graph")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                viewMode === "graph"
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
              }`}
            >
              <Network className="h-3.5 w-3.5" />
              Graph
            </button>
          </div>
        </div>

        {/* Main content area */}
        <div className="flex gap-6">
          {/* Left panel: list or graph */}
          <div className={selectedNode ? "flex-1" : "w-full"}>
            {viewMode === "list" ? (
              <ListView
                groups={groupedNodes}
                edges={graph.edges}
                nodes={graph.nodes}
                selectedNode={selectedNode}
                onSelectNode={setSelectedNode}
                onNavigate={(id) => router.push(`/assets/${id}`)}
              />
            ) : (
              <GraphView
                nodes={filteredNodes}
                edges={graph.edges}
                selectedNode={selectedNode}
                onSelectNode={setSelectedNode}
                onNavigate={(id) => router.push(`/assets/${id}`)}
              />
            )}
          </div>

          {/* Right panel: selected node details */}
          {selectedNode && (
            <div className="hidden w-80 shrink-0 lg:block">
              <NodeDetailPanel
                node={selectedNode}
                edges={selectedEdges}
                connectedNodes={connectedNodes}
                allNodes={graph.nodes}
                onClose={() => setSelectedNode(null)}
                onNavigate={(id) => router.push(`/assets/${id}`)}
                onSelectNode={setSelectedNode}
              />
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

// ── List View ───────────────────────────────────────────────────────

interface ListViewProps {
  groups: [string, GraphNode[]][];
  edges: GraphEdge[];
  nodes: GraphNode[];
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode | null) => void;
  onNavigate: (id: string) => void;
}

function ListView({
  groups,
  edges,
  nodes,
  selectedNode,
  onSelectNode,
  onNavigate,
}: ListViewProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const toggleGroup = (key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Build adjacency for showing connection badges
  const adjacency = useMemo(() => {
    const adj: Record<string, Set<string>> = {};
    for (const edge of edges) {
      if (!adj[edge.source]) adj[edge.source] = new Set();
      if (!adj[edge.target]) adj[edge.target] = new Set();
      adj[edge.source].add(edge.target);
      adj[edge.target].add(edge.source);
    }
    return adj;
  }, [edges]);

  const nodeMap = useMemo(() => {
    const map: Record<string, GraphNode> = {};
    for (const n of nodes) map[n.id] = n;
    return map;
  }, [nodes]);

  if (groups.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-gray-200 bg-white text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-500">
        No assets found
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {groups.map(([resourceType, groupNodes]) => {
        const isExpanded = expandedGroups.has(resourceType);
        const totalFindings = groupNodes.reduce(
          (sum, n) => sum + n.finding_count,
          0,
        );

        return (
          <div
            key={resourceType}
            className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
          >
            {/* Group header */}
            <button
              onClick={() => toggleGroup(resourceType)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-gray-400" />
              ) : (
                <ChevronRight className="h-4 w-4 text-gray-400" />
              )}
              <span className="flex-1 text-sm font-medium text-gray-900 dark:text-white">
                {formatResourceType(resourceType)}
              </span>
              <span className="text-xs text-gray-400 font-mono dark:text-gray-500">
                {resourceType}
              </span>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                {groupNodes.length}
              </span>
              {totalFindings > 0 && (
                <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                  {totalFindings} finding{totalFindings !== 1 ? "s" : ""}
                </span>
              )}
            </button>

            {/* Group content */}
            {isExpanded && (
              <div className="border-t border-gray-100 dark:border-gray-700">
                {groupNodes.map((node) => {
                  const connected = adjacency[node.id];
                  const connectedCount = connected?.size ?? 0;
                  const isSelected = selectedNode?.id === node.id;

                  return (
                    <div
                      key={node.id}
                      className={`flex items-center gap-3 border-b border-gray-50 px-4 py-3 last:border-b-0 transition-colors cursor-pointer dark:border-gray-700/50 ${
                        isSelected
                          ? "bg-blue-50 dark:bg-blue-900/20"
                          : "hover:bg-gray-50 dark:hover:bg-gray-700/30"
                      }`}
                      onClick={() => onSelectNode(isSelected ? null : node)}
                    >
                      {/* Provider dot */}
                      <span
                        className="h-3 w-3 shrink-0 rounded-full"
                        style={{
                          backgroundColor:
                            PROVIDER_COLORS[node.provider] ?? "#6b7280",
                        }}
                        title={node.provider}
                      />

                      {/* Name + region */}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                          {node.label}
                        </p>
                        {node.region && (
                          <p className="text-xs text-gray-400 dark:text-gray-500">
                            {node.region}
                          </p>
                        )}
                      </div>

                      {/* Connection count */}
                      {connectedCount > 0 && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400">
                          <Network className="h-3 w-3" />
                          {connectedCount}
                        </span>
                      )}

                      {/* Finding count */}
                      {node.finding_count > 0 && (
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                            node.highest_severity === "high"
                              ? "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                              : node.highest_severity === "medium"
                                ? "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                                : "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                          }`}
                        >
                          {node.highest_severity && (
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[node.highest_severity] ?? ""}`}
                            />
                          )}
                          {node.finding_count}
                        </span>
                      )}

                      {/* Navigate button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onNavigate(node.id);
                        }}
                        className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-600 dark:hover:text-gray-200"
                        title="View asset detail"
                      >
                        <ArrowRight className="h-4 w-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Graph View (SVG force-directed) ─────────────────────────────────

interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode | null) => void;
  onNavigate: (id: string) => void;
}

interface LayoutNode extends GraphNode {
  x: number;
  y: number;
}

function GraphView({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  onNavigate,
}: GraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 600 });

  // Responsive sizing
  useEffect(() => {
    const updateSize = () => {
      if (svgRef.current?.parentElement) {
        const rect = svgRef.current.parentElement.getBoundingClientRect();
        setDimensions({
          width: Math.max(rect.width, 400),
          height: Math.max(600, Math.min(rect.width * 0.6, 800)),
        });
      }
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // Layout: arrange nodes in concentric rings by resource type
  const layoutNodes: LayoutNode[] = useMemo(() => {
    if (nodes.length === 0) return [];

    const cx = dimensions.width / 2;
    const cy = dimensions.height / 2;

    // Group by resource type
    const groups: Record<string, GraphNode[]> = {};
    for (const node of nodes) {
      const key = node.resource_type;
      if (!groups[key]) groups[key] = [];
      groups[key].push(node);
    }

    const groupKeys = Object.keys(groups).sort();
    const numRings = groupKeys.length;

    if (numRings === 0) return [];

    const maxRadius = Math.min(cx, cy) - 40;
    const result: LayoutNode[] = [];

    groupKeys.forEach((key, ringIndex) => {
      const group = groups[key];
      const radius =
        numRings === 1
          ? maxRadius * 0.5
          : ((ringIndex + 1) / numRings) * maxRadius;
      const angleStep = (2 * Math.PI) / Math.max(group.length, 1);
      const startAngle = (ringIndex * Math.PI) / numRings; // offset each ring

      group.forEach((node, i) => {
        const angle = startAngle + i * angleStep;
        result.push({
          ...node,
          x: cx + radius * Math.cos(angle),
          y: cy + radius * Math.sin(angle),
        });
      });
    });

    return result;
  }, [nodes, dimensions]);

  const nodeMap = useMemo(() => {
    const map: Record<string, LayoutNode> = {};
    for (const n of layoutNodes) map[n.id] = n;
    return map;
  }, [layoutNodes]);

  // Filter edges to only those between visible nodes
  const visibleEdges = useMemo(() => {
    return edges.filter((e) => nodeMap[e.source] && nodeMap[e.target]);
  }, [edges, nodeMap]);

  if (nodes.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center rounded-xl border border-gray-200 bg-white text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-500">
        No assets to display
      </div>
    );
  }

  const isConnectedToHovered = (nodeId: string): boolean => {
    if (!hoveredNode) return false;
    return visibleEdges.some(
      (e) =>
        (e.source === hoveredNode && e.target === nodeId) ||
        (e.target === hoveredNode && e.source === nodeId),
    );
  };

  const isEdgeHighlighted = (edge: GraphEdge): boolean => {
    if (hoveredNode) {
      return edge.source === hoveredNode || edge.target === hoveredNode;
    }
    if (selectedNode) {
      return edge.source === selectedNode.id || edge.target === selectedNode.id;
    }
    return false;
  };

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="w-full"
        viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
      >
        {/* Background */}
        <rect
          width={dimensions.width}
          height={dimensions.height}
          className="fill-gray-50 dark:fill-gray-900"
        />

        {/* Grid pattern */}
        <defs>
          <pattern
            id="grid"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 40 0 L 0 0 0 40"
              fill="none"
              className="stroke-gray-200 dark:stroke-gray-700"
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <rect
          width={dimensions.width}
          height={dimensions.height}
          fill="url(#grid)"
          opacity="0.5"
        />

        {/* Edges */}
        <g>
          {visibleEdges.map((edge) => {
            const source = nodeMap[edge.source];
            const target = nodeMap[edge.target];
            if (!source || !target) return null;
            const highlighted = isEdgeHighlighted(edge);

            return (
              <line
                key={edge.id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={
                  highlighted
                    ? (RELATIONSHIP_COLORS[edge.type] ?? "#6b7280")
                    : "#d1d5db"
                }
                strokeWidth={highlighted ? 2 : 1}
                opacity={
                  hoveredNode || selectedNode ? (highlighted ? 1 : 0.15) : 0.4
                }
                className="transition-all duration-200"
              />
            );
          })}
        </g>

        {/* Nodes */}
        <g>
          {layoutNodes.map((node) => {
            const isHovered = hoveredNode === node.id;
            const isSelected = selectedNode?.id === node.id;
            const isConnected =
              isConnectedToHovered(node.id) ||
              (selectedNode &&
                visibleEdges.some(
                  (e) =>
                    (e.source === selectedNode.id && e.target === node.id) ||
                    (e.target === selectedNode.id && e.source === node.id),
                ));
            const isHighlighted = isHovered || isSelected || isConnected;
            const isDimmed = (hoveredNode || selectedNode) && !isHighlighted;

            const radius = Math.max(
              8,
              Math.min(20, 8 + node.finding_count * 2),
            );
            const color = PROVIDER_COLORS[node.provider] ?? "#6b7280";

            return (
              <g
                key={node.id}
                className="cursor-pointer transition-all duration-200"
                opacity={isDimmed ? 0.2 : 1}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => onSelectNode(isSelected ? null : node)}
                onDoubleClick={() => onNavigate(node.id)}
              >
                {/* Outer ring for selected */}
                {isSelected && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={radius + 5}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    strokeDasharray="4 2"
                    className="animate-spin"
                    style={{
                      animationDuration: "8s",
                      transformOrigin: `${node.x}px ${node.y}px`,
                    }}
                  />
                )}

                {/* Node circle */}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={radius}
                  fill={color}
                  opacity={isHovered || isSelected ? 1 : 0.8}
                  stroke={
                    node.highest_severity === "high"
                      ? "#ef4444"
                      : node.highest_severity === "medium"
                        ? "#f59e0b"
                        : "white"
                  }
                  strokeWidth={
                    node.highest_severity && node.finding_count > 0 ? 2.5 : 1.5
                  }
                />

                {/* Finding count badge */}
                {node.finding_count > 0 && (
                  <>
                    <circle
                      cx={node.x + radius * 0.7}
                      cy={node.y - radius * 0.7}
                      r={7}
                      fill={
                        node.highest_severity === "high"
                          ? "#ef4444"
                          : node.highest_severity === "medium"
                            ? "#f59e0b"
                            : "#3b82f6"
                      }
                    />
                    <text
                      x={node.x + radius * 0.7}
                      y={node.y - radius * 0.7}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="white"
                      fontSize="8"
                      fontWeight="bold"
                    >
                      {node.finding_count > 9 ? "9+" : node.finding_count}
                    </text>
                  </>
                )}

                {/* Label on hover */}
                {(isHovered || isSelected) && (
                  <>
                    <rect
                      x={node.x - 60}
                      y={node.y + radius + 4}
                      width={120}
                      height={32}
                      rx={6}
                      fill="white"
                      stroke="#e5e7eb"
                      strokeWidth="1"
                      className="dark:fill-gray-800 dark:stroke-gray-600"
                    />
                    <text
                      x={node.x}
                      y={node.y + radius + 16}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="10"
                      fontWeight="600"
                      className="fill-gray-900 dark:fill-white"
                    >
                      {node.label.length > 18
                        ? node.label.substring(0, 16) + "..."
                        : node.label}
                    </text>
                    <text
                      x={node.x}
                      y={node.y + radius + 28}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="8"
                      className="fill-gray-400 dark:fill-gray-500"
                    >
                      {shortResourceType(node.resource_type)}
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-6 border-t border-gray-100 px-4 py-2 text-xs text-gray-500 dark:border-gray-700 dark:text-gray-400">
        <span className="font-medium">Providers:</span>
        {Object.entries(PROVIDER_COLORS).map(([prov, color]) => (
          <span key={prov} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            {prov.charAt(0).toUpperCase() + prov.slice(1)}
          </span>
        ))}
        <span className="mx-2 text-gray-300 dark:text-gray-600">|</span>
        <span className="font-medium">Size:</span>
        <span>= finding count</span>
        <span className="mx-2 text-gray-300 dark:text-gray-600">|</span>
        <span>Double-click to view detail</span>
      </div>
    </div>
  );
}

// ── Node Detail Panel ───────────────────────────────────────────────

interface NodeDetailPanelProps {
  node: GraphNode;
  edges: GraphEdge[];
  connectedNodes: GraphNode[];
  allNodes: GraphNode[];
  onClose: () => void;
  onNavigate: (id: string) => void;
  onSelectNode: (node: GraphNode) => void;
}

function NodeDetailPanel({
  node,
  edges,
  connectedNodes,
  allNodes,
  onClose,
  onNavigate,
  onSelectNode,
}: NodeDetailPanelProps) {
  const nodeMap = useMemo(() => {
    const map: Record<string, GraphNode> = {};
    for (const n of allNodes) map[n.id] = n;
    return map;
  }, [allNodes]);

  return (
    <div className="sticky top-6 space-y-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-gray-900 dark:text-white">
            {node.label}
          </h3>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            {formatResourceType(node.resource_type)}
          </p>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-200"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Info */}
      <div className="space-y-2 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-gray-500 dark:text-gray-400">Provider</span>
          <span
            className={`rounded-full px-2 py-0.5 font-medium ${PROVIDER_BG[node.provider] ?? "bg-gray-100 dark:bg-gray-700"}`}
            style={{ color: PROVIDER_COLORS[node.provider] ?? "#6b7280" }}
          >
            {node.provider}
          </span>
        </div>
        {node.region && (
          <div className="flex items-center justify-between">
            <span className="text-gray-500 dark:text-gray-400">Region</span>
            <span className="text-gray-900 dark:text-white">{node.region}</span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-gray-500 dark:text-gray-400">Findings</span>
          <span
            className={`font-medium ${node.finding_count > 0 ? (SEVERITY_COLORS[node.highest_severity ?? ""] ?? "text-gray-900 dark:text-white") : "text-green-600 dark:text-green-400"}`}
          >
            {node.finding_count > 0 ? node.finding_count : "None"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-gray-500 dark:text-gray-400">Connections</span>
          <span className="text-gray-900 dark:text-white">
            {connectedNodes.length}
          </span>
        </div>
      </div>

      {/* Action */}
      <button
        onClick={() => onNavigate(node.id)}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-700"
      >
        View Asset Detail
        <ArrowRight className="h-3.5 w-3.5" />
      </button>

      {/* Connected assets */}
      {edges.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300">
            Relationships ({edges.length})
          </h4>
          <div className="max-h-64 space-y-1.5 overflow-y-auto">
            {edges.map((edge) => {
              const isSource = edge.source === node.id;
              const otherId = isSource ? edge.target : edge.source;
              const otherNode = nodeMap[otherId];
              if (!otherNode) return null;

              return (
                <button
                  key={edge.id}
                  onClick={() => onSelectNode(otherNode)}
                  className="flex w-full items-center gap-2 rounded-lg border border-gray-100 p-2 text-left transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50"
                >
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{
                      backgroundColor:
                        RELATIONSHIP_COLORS[edge.type] ?? "#6b7280",
                    }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-gray-900 dark:text-white">
                      {otherNode.label}
                    </p>
                    <p className="text-[10px] text-gray-400 dark:text-gray-500">
                      {isSource ? "" : ""}
                      {RELATIONSHIP_LABELS[edge.type] ?? edge.type}
                      {isSource ? " (outgoing)" : " (incoming)"}
                    </p>
                  </div>
                  {otherNode.finding_count > 0 && (
                    <span
                      className={`text-[10px] font-medium ${SEVERITY_COLORS[otherNode.highest_severity ?? ""] ?? "text-gray-500"}`}
                    >
                      {otherNode.finding_count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
