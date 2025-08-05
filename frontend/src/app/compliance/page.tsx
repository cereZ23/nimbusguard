"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Loader2, Plus, Trash2, TrendingUp, X } from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import SeverityBadge from "@/components/ui/severity-badge";
import StatusBadge from "@/components/ui/status-badge";
import ErrorState from "@/components/ui/error-state";
import { useAuth } from "@/lib/auth";
import api from "@/lib/api";
import type {
  ComplianceTrendPoint,
  ComplianceTrendResponse,
  Control,
  ControlComplianceItem,
  ControlWithCounts,
  CustomFramework,
  CustomFrameworkCompliance,
  Finding,
} from "@/types";

// Lazy load Recharts-heavy trend chart to reduce initial bundle size
const ComplianceTrendChart = dynamic(
  () => import("@/components/compliance/compliance-trend-chart"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[280px] animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
    ),
  },
);

// --- Framework configuration ---

type FrameworkKey = "cis-lite" | "soc2" | "nist" | "iso27001";

interface FrameworkConfig {
  key: FrameworkKey;
  label: string;
  description: string;
}

const BUILT_IN_FRAMEWORKS: FrameworkConfig[] = [
  {
    key: "cis-lite",
    label: "CIS Azure",
    description: "CIS Benchmark for Microsoft Azure - Lite",
  },
  {
    key: "soc2",
    label: "SOC 2 Type II",
    description: "AICPA Trust Service Criteria",
  },
  {
    key: "nist",
    label: "NIST 800-53",
    description: "NIST Special Publication 800-53 Rev. 5",
  },
  {
    key: "iso27001",
    label: "ISO 27001",
    description: "ISO/IEC 27001:2022 Annex A Controls",
  },
];

// Map frontend framework key to API framework key for trend endpoint
const TREND_FRAMEWORK_MAP: Record<FrameworkKey, string> = {
  "cis-lite": "cis_azure",
  soc2: "soc2",
  nist: "nist",
  iso27001: "iso27001",
};

type TrendPeriod = "30d" | "90d" | "180d";

const TREND_PERIODS: { value: TrendPeriod; label: string }[] = [
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "180d", label: "180 days" },
];

// SOC 2 Trust Service Criteria grouping labels
const SOC2_GROUPS: Record<string, string> = {
  "CC6.1": "CC6.1 - Logical and Physical Access Controls",
  "CC6.2": "CC6.2 - User Registration and Authorization",
  "CC6.3": "CC6.3 - Role-Based Access and Least Privilege",
  "CC6.6": "CC6.6 - Network Security and Boundary Protection",
  "CC6.7": "CC6.7 - Data Encryption and Transmission Security",
  "CC6.8": "CC6.8 - Malware and Endpoint Protection",
  "CC7.1": "CC7.1 - Threat Detection and Prevention",
  "CC7.2": "CC7.2 - System Monitoring and Anomaly Detection",
  "CC7.3": "CC7.3 - Security Event Evaluation",
  "A1.2": "A1.2 - Recovery and Continuity",
};

// NIST 800-53 family grouping labels
const NIST_GROUPS: Record<string, string> = {
  "AC-2": "AC-2 - Account Management",
  "AC-3": "AC-3 - Access Enforcement",
  "AC-4": "AC-4 - Information Flow Enforcement",
  "AC-6": "AC-6 - Least Privilege",
  "AU-2": "AU-2 - Audit Events",
  "AU-3": "AU-3 - Content of Audit Records",
  "AU-4": "AU-4 - Audit Storage Capacity",
  "AU-6": "AU-6 - Audit Review, Analysis, and Reporting",
  "AU-11": "AU-11 - Audit Record Retention",
  "AU-12": "AU-12 - Audit Generation",
  "CM-6": "CM-6 - Configuration Settings",
  "CM-7": "CM-7 - Least Functionality",
  "CP-7": "CP-7 - Alternate Processing Site",
  "CP-9": "CP-9 - Information System Backup",
  "CP-10": "CP-10 - Information System Recovery",
  "IA-2": "IA-2 - Identification and Authentication",
  "IA-2(1)": "IA-2(1) - Multi-Factor Authentication to Privileged Accounts",
  "IA-2(2)": "IA-2(2) - Multi-Factor Authentication to Non-Privileged Accounts",
  "IA-5": "IA-5 - Authenticator Management",
  "SC-5": "SC-5 - Denial of Service Protection",
  "SC-7": "SC-7 - Boundary Protection",
  "SC-7(5)": "SC-7(5) - Deny by Default",
  "SC-8": "SC-8 - Transmission Confidentiality and Integrity",
  "SC-8(1)": "SC-8(1) - Cryptographic Protection",
  "SC-12": "SC-12 - Cryptographic Key Management",
  "SC-12(1)": "SC-12(1) - Availability of Keys",
  "SC-12(3)": "SC-12(3) - Asymmetric Key Generation",
  "SC-28": "SC-28 - Protection of Information at Rest",
  "SI-2": "SI-2 - Flaw Remediation",
  "SI-2(2)": "SI-2(2) - Automated Flaw Remediation Status",
  "SI-3": "SI-3 - Malicious Code Protection",
  "SI-3(1)": "SI-3(1) - Central Management",
  "SI-4": "SI-4 - Information System Monitoring",
  "SI-7": "SI-7 - Software, Firmware, and Information Integrity",
  "SI-7(1)": "SI-7(1) - Integrity Checks",
};

// ISO 27001:2022 Annex A control grouping labels
const ISO27001_GROUPS: Record<string, string> = {
  "A.5.15": "A.5.15 - Access Control",
  "A.5.16": "A.5.16 - Identity Management",
  "A.5.17": "A.5.17 - Authentication Information",
  "A.5.18": "A.5.18 - Access Rights",
  "A.5.25": "A.5.25 - Assessment and Decision on Information Security Events",
  "A.5.29": "A.5.29 - Information Security During Disruption",
  "A.5.33": "A.5.33 - Protection of Records",
  "A.8.2": "A.8.2 - Privileged Access Rights",
  "A.8.3": "A.8.3 - Information Access Restriction",
  "A.8.5": "A.8.5 - Secure Authentication",
  "A.8.7": "A.8.7 - Protection Against Malware",
  "A.8.8": "A.8.8 - Management of Technical Vulnerabilities",
  "A.8.9": "A.8.9 - Configuration Management",
  "A.8.10": "A.8.10 - Information Deletion",
  "A.8.13": "A.8.13 - Information Backup",
  "A.8.14": "A.8.14 - Redundancy of Information Processing Facilities",
  "A.8.15": "A.8.15 - Logging",
  "A.8.16": "A.8.16 - Monitoring Activities",
  "A.8.19": "A.8.19 - Installation of Software on Operational Systems",
  "A.8.20": "A.8.20 - Network Security",
  "A.8.21": "A.8.21 - Security of Network Services",
  "A.8.22": "A.8.22 - Segregation of Networks",
  "A.8.23": "A.8.23 - Web Filtering",
  "A.8.24": "A.8.24 - Use of Cryptography",
  "A.8.26": "A.8.26 - Application Security Requirements",
  "A.8.27": "A.8.27 - Secure System Architecture and Engineering Principles",
};

// --- Helper components ---

function PassRateBar({
  passCount,
  totalCount,
}: {
  passCount: number;
  totalCount: number;
}) {
  if (totalCount === 0) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-2 w-20 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700" />
        <span className="text-xs text-gray-400 dark:text-gray-500">--</span>
      </div>
    );
  }

  const rate = Math.round((passCount / totalCount) * 100);
  const failCount = totalCount - passCount;

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className="h-full rounded-full bg-green-500 transition-all"
          style={{ width: `${rate}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 dark:text-gray-400">
        {passCount}/{passCount + failCount}
      </span>
    </div>
  );
}

function StatusLabel({ control }: { control: ControlWithCounts }) {
  if (control.total_count === 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 dark:text-gray-500">
        <span className="h-1.5 w-1.5 rounded-full bg-gray-300 dark:bg-gray-600" />
        No data
      </span>
    );
  }
  if (control.fail_count > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-600 dark:text-red-400">
        <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
        {control.fail_count} failing
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-600 dark:text-green-400">
      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
      All passing
    </span>
  );
}

function CustomStatusLabel({ item }: { item: ControlComplianceItem }) {
  if (item.total_count === 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 dark:text-gray-500">
        <span className="h-1.5 w-1.5 rounded-full bg-gray-300 dark:bg-gray-600" />
        No data
      </span>
    );
  }
  if (item.fail_count > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-600 dark:text-red-400">
        <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
        {item.fail_count} failing
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-600 dark:text-green-400">
      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
      All passing
    </span>
  );
}

// --- Grouping logic ---

interface ControlGroup {
  key: string;
  label: string;
  controls: ControlWithCounts[];
}

function groupControlsByFramework(
  controls: ControlWithCounts[],
  framework: FrameworkKey,
): ControlGroup[] {
  if (framework === "cis-lite") {
    // No grouping for CIS, return a single flat group
    return [{ key: "all", label: "", controls }];
  }

  const groupLabels =
    framework === "soc2"
      ? SOC2_GROUPS
      : framework === "nist"
        ? NIST_GROUPS
        : ISO27001_GROUPS;
  const groupMap = new Map<string, Set<string>>();

  // Build groups: each control can appear in multiple groups
  for (const control of controls) {
    const refs = control.framework_mappings?.[framework] ?? [];
    for (const ref of refs) {
      if (!groupMap.has(ref)) {
        groupMap.set(ref, new Set());
      }
      groupMap.get(ref)!.add(control.id);
    }
  }

  // Sort group keys by their natural order
  const sortedKeys = Array.from(groupMap.keys()).sort((a, b) =>
    a.localeCompare(b, undefined, { numeric: true }),
  );

  const controlById = new Map(controls.map((c) => [c.id, c]));

  return sortedKeys.map((key) => ({
    key,
    label: groupLabels[key] ?? key,
    controls: Array.from(groupMap.get(key)!)
      .map((id) => controlById.get(id)!)
      .filter(Boolean)
      .sort((a, b) => a.code.localeCompare(b.code)),
  }));
}

// --- Custom framework grouping for compliance items ---

interface CustomControlGroup {
  key: string;
  label: string;
  items: ControlComplianceItem[];
}

function groupCustomComplianceByGroup(
  items: ControlComplianceItem[],
): CustomControlGroup[] {
  const groupMap = new Map<string, ControlComplianceItem[]>();
  for (const item of items) {
    const groupKey = item.group || "Ungrouped";
    if (!groupMap.has(groupKey)) {
      groupMap.set(groupKey, []);
    }
    groupMap.get(groupKey)!.push(item);
  }

  const sortedKeys = Array.from(groupMap.keys()).sort((a, b) =>
    a.localeCompare(b),
  );

  return sortedKeys.map((key) => ({
    key,
    label: key,
    items: groupMap
      .get(key)!
      .sort((a, b) => a.control_code.localeCompare(b.control_code)),
  }));
}

// --- Framework Builder Modal ---

interface MappingEntry {
  control_code: string;
  group: string;
  reference: string;
}

function FrameworkBuilderModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (fw: CustomFramework) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [allControls, setAllControls] = useState<Control[]>([]);
  const [loadingControls, setLoadingControls] = useState(true);
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());
  const [mappingDetails, setMappingDetails] = useState<
    Record<string, { group: string; reference: string }>
  >({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [controlSearch, setControlSearch] = useState("");

  useEffect(() => {
    api
      .get("/controls", { params: { size: 200, framework: "cis-lite" } })
      .then((res) => {
        const data = (res.data?.data as Control[]) ?? [];
        setAllControls(data);
      })
      .catch(() => {
        setAllControls([]);
      })
      .finally(() => setLoadingControls(false));
  }, []);

  const filteredControls = useMemo(() => {
    if (!controlSearch.trim()) return allControls;
    const q = controlSearch.toLowerCase().trim();
    return allControls.filter(
      (c) =>
        c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
    );
  }, [allControls, controlSearch]);

  const toggleControl = (code: string) => {
    setSelectedCodes((prev) => {
      const next = new Set(Array.from(prev));
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      return next;
    });
  };

  const selectAll = () => {
    const codes = new Set(filteredControls.map((c) => c.code));
    setSelectedCodes(
      (prev) => new Set([...Array.from(prev), ...Array.from(codes)]),
    );
  };

  const deselectAll = () => {
    const codesToRemove = filteredControls.map((c) => c.code);
    setSelectedCodes((prev) => {
      const next = new Set(Array.from(prev));
      codesToRemove.forEach((code) => next.delete(code));
      return next;
    });
  };

  const updateMapping = (
    code: string,
    field: "group" | "reference",
    value: string,
  ) => {
    setMappingDetails((prev) => ({
      ...prev,
      [code]: {
        ...prev[code],
        group: prev[code]?.group ?? "",
        reference: prev[code]?.reference ?? "",
        [field]: value,
      },
    }));
  };

  const handleSave = async () => {
    if (!name.trim() || selectedCodes.size === 0) return;

    setSaving(true);
    setSaveError(null);

    const controlMappings: MappingEntry[] = Array.from(selectedCodes).map(
      (code) => ({
        control_code: code,
        group: mappingDetails[code]?.group ?? "",
        reference: mappingDetails[code]?.reference ?? "",
      }),
    );

    try {
      const res = await api.post("/custom-frameworks", {
        name: name.trim(),
        description: description.trim() || null,
        control_mappings: controlMappings,
      });
      const created = res.data?.data as CustomFramework;
      onCreated(created);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setSaveError(
        axiosErr?.response?.data?.detail ?? "Failed to create framework",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-white shadow-2xl dark:bg-gray-800">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Create Custom Framework
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="space-y-5">
            {/* Name */}
            <div>
              <label
                htmlFor="fw-name"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Framework Name *
              </label>
              <input
                id="fw-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                placeholder="e.g., Internal Security Baseline"
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:placeholder:text-gray-500"
              />
            </div>

            {/* Description */}
            <div>
              <label
                htmlFor="fw-desc"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Description
              </label>
              <textarea
                id="fw-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                placeholder="Describe the purpose of this framework..."
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:placeholder:text-gray-500"
              />
            </div>

            {/* Control selector */}
            <div>
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Select Controls * ({selectedCodes.size} selected)
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={selectAll}
                    className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    Select all
                  </button>
                  <span className="text-xs text-gray-300 dark:text-gray-600">
                    |
                  </span>
                  <button
                    type="button"
                    onClick={deselectAll}
                    className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    Deselect all
                  </button>
                </div>
              </div>

              {/* Search controls */}
              <input
                type="text"
                value={controlSearch}
                onChange={(e) => setControlSearch(e.target.value)}
                placeholder="Search controls by code or name..."
                className="mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:placeholder:text-gray-500"
              />

              {loadingControls ? (
                <div className="mt-3 flex items-center gap-2 text-sm text-gray-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading controls...
                </div>
              ) : (
                <div className="mt-2 max-h-72 overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-700">
                  {filteredControls.map((ctrl) => {
                    const isSelected = selectedCodes.has(ctrl.code);
                    return (
                      <div
                        key={ctrl.code}
                        className="border-b border-gray-100 last:border-b-0 dark:border-gray-700"
                      >
                        <div className="flex items-center gap-3 px-3 py-2">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleControl(ctrl.code)}
                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
                          />
                          <span className="w-24 flex-shrink-0 font-mono text-xs text-gray-500 dark:text-gray-400">
                            {ctrl.code}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-sm text-gray-800 dark:text-gray-200">
                            {ctrl.name}
                          </span>
                          <SeverityBadge severity={ctrl.severity} />
                        </div>
                        {/* Group & Reference fields shown when selected */}
                        {isSelected && (
                          <div className="flex gap-2 bg-gray-50 px-3 pb-2 pl-10 dark:bg-gray-800/50">
                            <input
                              type="text"
                              value={mappingDetails[ctrl.code]?.group ?? ""}
                              onChange={(e) =>
                                updateMapping(
                                  ctrl.code,
                                  "group",
                                  e.target.value,
                                )
                              }
                              placeholder="Group (e.g., Access Control)"
                              className="w-1/2 rounded border border-gray-200 bg-white px-2 py-1 text-xs placeholder:text-gray-400 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:placeholder:text-gray-500"
                            />
                            <input
                              type="text"
                              value={mappingDetails[ctrl.code]?.reference ?? ""}
                              onChange={(e) =>
                                updateMapping(
                                  ctrl.code,
                                  "reference",
                                  e.target.value,
                                )
                              }
                              placeholder="Reference (e.g., AC-1)"
                              className="w-1/2 rounded border border-gray-200 bg-white px-2 py-1 text-xs placeholder:text-gray-400 focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:placeholder:text-gray-500"
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 px-6 py-4 dark:border-gray-700">
          {saveError && (
            <p className="mb-3 text-sm text-red-600 dark:text-red-400">
              {saveError}
            </p>
          )}
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !name.trim() || selectedCodes.size === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Create Framework
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Main component ---

// Discriminated union for the active tab
type ActiveTab =
  | { type: "builtin"; key: FrameworkKey }
  | { type: "custom"; id: string };

export default function CompliancePage() {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  // Built-in framework state
  const [controls, setControls] = useState<ControlWithCounts[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<ActiveTab>({
    type: "builtin",
    key: "cis-lite",
  });
  const [findingsCache, setFindingsCache] = useState<Record<string, Finding[]>>(
    {},
  );
  const [findingsLoading, setFindingsLoading] = useState<
    Record<string, boolean>
  >({});
  const [trendPeriod, setTrendPeriod] = useState<TrendPeriod>("30d");
  const [trendData, setTrendData] = useState<ComplianceTrendPoint[]>([]);
  const [trendLoading, setTrendLoading] = useState(false);

  // Custom framework state
  const [customFrameworks, setCustomFrameworks] = useState<CustomFramework[]>(
    [],
  );
  const [customCompliance, setCustomCompliance] =
    useState<CustomFrameworkCompliance | null>(null);
  const [customLoading, setCustomLoading] = useState(false);
  const [showBuilder, setShowBuilder] = useState(false);

  // Fetch custom frameworks on mount
  useEffect(() => {
    api
      .get("/custom-frameworks", { params: { size: 100 } })
      .then((res) => {
        const data = (res.data?.data as CustomFramework[]) ?? [];
        setCustomFrameworks(data);
      })
      .catch(() => {
        // Silently ignore -- custom frameworks are optional
      });
  }, []);

  const fetchTrend = useCallback(
    (framework: FrameworkKey, period: TrendPeriod) => {
      setTrendLoading(true);
      const apiFramework = TREND_FRAMEWORK_MAP[framework];
      api
        .get("/dashboard/compliance-trend", {
          params: { framework: apiFramework, period },
        })
        .then((res) => {
          const response = res.data?.data as ComplianceTrendResponse | null;
          setTrendData(response?.data ?? []);
        })
        .catch(() => {
          setTrendData([]);
        })
        .finally(() => setTrendLoading(false));
    },
    [],
  );

  const fetchControls = useCallback((framework: FrameworkKey) => {
    setError(null);
    setIsLoading(true);
    setExpandedId(null);
    api
      .get("/controls", { params: { size: 200, framework } })
      .then((res) => {
        const data = res.data?.data as ControlWithCounts[] | null;
        setControls(data ?? []);
      })
      .catch((err) =>
        setError(
          err?.response?.data?.error || "Failed to load compliance controls",
        ),
      )
      .finally(() => setIsLoading(false));
  }, []);

  const fetchCustomCompliance = useCallback((frameworkId: string) => {
    setCustomLoading(true);
    setCustomCompliance(null);
    setError(null);
    api
      .get(`/custom-frameworks/${frameworkId}/compliance`)
      .then((res) => {
        const data = res.data?.data as CustomFrameworkCompliance;
        setCustomCompliance(data);
      })
      .catch((err) =>
        setError(
          err?.response?.data?.error ||
            "Failed to load custom framework compliance",
        ),
      )
      .finally(() => setCustomLoading(false));
  }, []);

  // Handle tab changes
  useEffect(() => {
    if (activeTab.type === "builtin") {
      setCustomCompliance(null);
      fetchControls(activeTab.key);
    } else {
      setControls([]);
      fetchCustomCompliance(activeTab.id);
    }
  }, [activeTab, fetchControls, fetchCustomCompliance]);

  // Fetch trend only for built-in frameworks
  useEffect(() => {
    if (activeTab.type === "builtin") {
      fetchTrend(activeTab.key, trendPeriod);
    }
  }, [activeTab, trendPeriod, fetchTrend]);

  const handleBuiltinTabChange = (fw: FrameworkKey) => {
    if (activeTab.type === "builtin" && activeTab.key === fw) return;
    setActiveTab({ type: "builtin", key: fw });
    setSeverityFilter("all");
    setSearchQuery("");
  };

  const handleCustomTabChange = (id: string) => {
    if (activeTab.type === "custom" && activeTab.id === id) return;
    setActiveTab({ type: "custom", id });
    setSeverityFilter("all");
    setSearchQuery("");
  };

  const handleDeleteCustomFramework = async (id: string) => {
    try {
      await api.delete(`/custom-frameworks/${id}`);
      setCustomFrameworks((prev) => prev.filter((f) => f.id !== id));
      // If we deleted the active framework, switch to CIS
      if (activeTab.type === "custom" && activeTab.id === id) {
        setActiveTab({ type: "builtin", key: "cis-lite" });
      }
    } catch {
      // Ignore delete errors
    }
  };

  const handleFrameworkCreated = (fw: CustomFramework) => {
    setCustomFrameworks((prev) => [fw, ...prev]);
    setShowBuilder(false);
    setActiveTab({ type: "custom", id: fw.id });
  };

  // --- Built-in framework computed values ---
  const filteredControls = useMemo(() => {
    let result = controls;

    if (severityFilter !== "all") {
      result = result.filter((c) => c.severity === severityFilter);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(query) ||
          c.code.toLowerCase().includes(query),
      );
    }

    return result;
  }, [controls, severityFilter, searchQuery]);

  const controlGroups = useMemo(() => {
    if (activeTab.type !== "builtin") return [];
    return groupControlsByFramework(filteredControls, activeTab.key);
  }, [filteredControls, activeTab]);

  const frameworkSummary = useMemo(() => {
    const totalPassing = controls.filter(
      (c) => c.total_count > 0 && c.fail_count === 0,
    ).length;
    const totalFailing = controls.filter((c) => c.fail_count > 0).length;
    return {
      passing: totalPassing,
      failing: totalFailing,
      total: controls.length,
    };
  }, [controls]);

  // --- Custom framework computed values ---
  const filteredCustomControls = useMemo(() => {
    if (!customCompliance) return [];
    let result = customCompliance.controls;

    if (severityFilter !== "all") {
      result = result.filter((c) => c.severity === severityFilter);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      result = result.filter(
        (c) =>
          c.control_name.toLowerCase().includes(query) ||
          c.control_code.toLowerCase().includes(query),
      );
    }

    return result;
  }, [customCompliance, severityFilter, searchQuery]);

  const customGroups = useMemo(
    () => groupCustomComplianceByGroup(filteredCustomControls),
    [filteredCustomControls],
  );

  const customSummary = useMemo(() => {
    if (!customCompliance) return { passing: 0, failing: 0, total: 0 };
    return {
      passing: customCompliance.passing_controls,
      failing: customCompliance.failing_controls,
      total: customCompliance.total_controls,
    };
  }, [customCompliance]);

  const handleToggle = (id: string) => {
    const willExpand = expandedId !== id;
    setExpandedId(willExpand ? id : null);

    if (willExpand && !findingsCache[id]) {
      setFindingsLoading((prev) => ({ ...prev, [id]: true }));
      api
        .get(`/controls/${id}/findings`, { params: { size: 10 } })
        .then((res) => {
          const data = (res.data?.data as Finding[] | null) ?? [];
          setFindingsCache((prev) => ({ ...prev, [id]: data }));
        })
        .catch(() => {
          setFindingsCache((prev) => ({ ...prev, [id]: [] }));
        })
        .finally(() => {
          setFindingsLoading((prev) => ({ ...prev, [id]: false }));
        });
    }
  };

  // Determine which summary to use based on active tab
  const currentSummary =
    activeTab.type === "builtin" ? frameworkSummary : customSummary;
  const currentProgressPct =
    currentSummary.total > 0
      ? Math.round((currentSummary.passing / currentSummary.total) * 100)
      : 0;
  const currentLoading =
    activeTab.type === "builtin" ? isLoading : customLoading;
  const currentControlCount =
    activeTab.type === "builtin"
      ? controls.length
      : (customCompliance?.total_controls ?? 0);

  // Determine active label/description
  const activeLabel =
    activeTab.type === "builtin"
      ? BUILT_IN_FRAMEWORKS.find((f) => f.key === activeTab.key)!.label
      : (customFrameworks.find((f) => f.id === activeTab.id)?.name ?? "Custom");
  const activeDescription =
    activeTab.type === "builtin"
      ? BUILT_IN_FRAMEWORKS.find((f) => f.key === activeTab.key)!.description
      : (customFrameworks.find((f) => f.id === activeTab.id)?.description ??
        "");

  const severityBorderColor = (severity: string) => {
    switch (severity) {
      case "high":
        return "border-l-red-400";
      case "medium":
        return "border-l-amber-400";
      case "low":
        return "border-l-blue-400";
      default:
        return "border-l-gray-300";
    }
  };

  const renderControlRow = (control: ControlWithCounts) => {
    const isExpanded = expandedId === control.id;
    const passRate =
      control.total_count > 0
        ? Math.round((control.pass_count / control.total_count) * 100)
        : 0;

    return (
      <div key={control.id}>
        {/* Collapsed row */}
        <button
          type="button"
          onClick={() => handleToggle(control.id)}
          className={`flex w-full items-center gap-4 border-l-4 px-4 py-3.5 text-left transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50 ${severityBorderColor(control.severity)}`}
        >
          {/* Expand/collapse chevron */}
          <svg
            className={`h-4 w-4 flex-shrink-0 text-gray-400 transition-transform dark:text-gray-500 ${
              isExpanded ? "rotate-90" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8.25 4.5l7.5 7.5-7.5 7.5"
            />
          </svg>

          {/* Code */}
          <span className="w-28 flex-shrink-0 font-mono text-xs text-gray-500 dark:text-gray-400">
            {control.code}
          </span>

          {/* Name */}
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900 dark:text-gray-100">
            {control.name}
          </span>

          {/* Severity badge */}
          <div className="flex-shrink-0">
            <SeverityBadge severity={control.severity} />
          </div>

          {/* Pass rate */}
          <div className="flex-shrink-0">
            <PassRateBar
              passCount={control.pass_count}
              totalCount={control.total_count}
            />
          </div>

          {/* Status label */}
          <div className="w-24 flex-shrink-0 text-right">
            <StatusLabel control={control} />
          </div>
        </button>

        {/* Expanded detail panel */}
        {isExpanded && (
          <div className="border-t border-gray-100 bg-gray-50 px-4 py-4 pl-12 dark:border-gray-700 dark:bg-gray-900/50">
            <div className="space-y-3">
              {/* Description */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Description
                </h4>
                <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">
                  {control.description}
                </p>
              </div>

              {/* Framework references */}
              {control.framework_mappings &&
                Object.keys(control.framework_mappings).length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      Framework References
                    </h4>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {Object.entries(control.framework_mappings).map(
                        ([fw, refs]) => (
                          <div key={fw} className="flex items-center gap-1">
                            <span className="inline-flex rounded bg-gray-200 px-1.5 py-0.5 text-xs font-semibold uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                              {fw}
                            </span>
                            {refs.map((ref) => (
                              <span
                                key={ref}
                                className="inline-flex rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                              >
                                {ref}
                              </span>
                            ))}
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}

              {/* Remediation hint */}
              {control.remediation_hint && (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                    Remediation
                  </h4>
                  <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">
                    {control.remediation_hint}
                  </p>
                </div>
              )}

              {/* Findings drill-down table */}
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Affected Resources
                </h4>
                {findingsLoading[control.id] ? (
                  <div className="mt-2 flex items-center gap-2 text-sm text-gray-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading findings...
                  </div>
                ) : findingsCache[control.id]?.length ? (
                  <div className="mt-2 overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
                          <th className="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">
                            Title
                          </th>
                          <th className="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">
                            Severity
                          </th>
                          <th className="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">
                            Status
                          </th>
                          <th className="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">
                            Last Evaluated
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {findingsCache[control.id].map((f) => (
                          <tr
                            key={f.id}
                            onClick={() => router.push(`/findings/${f.id}`)}
                            className="cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-700/50"
                          >
                            <td className="max-w-xs truncate px-3 py-2 font-medium text-gray-900 dark:text-gray-100">
                              {f.title}
                            </td>
                            <td className="px-3 py-2">
                              <SeverityBadge severity={f.severity} />
                            </td>
                            <td className="px-3 py-2">
                              <StatusBadge status={f.status} />
                            </td>
                            <td className="px-3 py-2 text-gray-500 dark:text-gray-400">
                              {new Date(
                                f.last_evaluated_at,
                              ).toLocaleDateString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-gray-400">
                    No findings for this control.
                  </p>
                )}
              </div>

              {/* Stats + link */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                  <span>
                    Pass: {control.pass_count} / {control.total_count}
                  </span>
                  <span>Fail: {control.fail_count}</span>
                  <span>Rate: {passRate}%</span>
                </div>
                <Link
                  href={`/findings?control_id=${control.id}`}
                  className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
                >
                  View all {control.total_count} findings
                  <svg
                    className="h-3 w-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                    />
                  </svg>
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderCustomControlRow = (item: ControlComplianceItem) => {
    return (
      <div
        key={item.control_code}
        className={`flex w-full items-center gap-4 border-l-4 px-4 py-3.5 text-left ${severityBorderColor(item.severity)}`}
      >
        {/* Code */}
        <span className="w-28 flex-shrink-0 font-mono text-xs text-gray-500 dark:text-gray-400">
          {item.control_code}
        </span>

        {/* Name */}
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900 dark:text-gray-100">
          {item.control_name}
        </span>

        {/* Reference */}
        {item.reference && (
          <span className="flex-shrink-0 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
            {item.reference}
          </span>
        )}

        {/* Severity badge */}
        <div className="flex-shrink-0">
          <SeverityBadge severity={item.severity} />
        </div>

        {/* Pass rate */}
        <div className="flex-shrink-0">
          <PassRateBar
            passCount={item.pass_count}
            totalCount={item.total_count}
          />
        </div>

        {/* Status label */}
        <div className="w-24 flex-shrink-0 text-right">
          <CustomStatusLabel item={item} />
        </div>
      </div>
    );
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Compliance
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Security controls and compliance posture for your cloud
              environment
            </p>
          </div>
          <div className="flex items-center gap-3">
            {isAdmin && (
              <button
                type="button"
                onClick={() => setShowBuilder(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700"
              >
                <Plus className="h-4 w-4" />
                Create Framework
              </button>
            )}
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {currentControlCount} controls
            </div>
          </div>
        </div>

        {/* Framework tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav
            className="-mb-px flex flex-wrap gap-x-6"
            aria-label="Compliance frameworks"
          >
            {/* Built-in framework tabs */}
            {BUILT_IN_FRAMEWORKS.map((fw) => (
              <button
                key={fw.key}
                type="button"
                onClick={() => handleBuiltinTabChange(fw.key)}
                className={`whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium transition-colors ${
                  activeTab.type === "builtin" && activeTab.key === fw.key
                    ? "border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:border-gray-600 dark:hover:text-gray-300"
                }`}
              >
                {fw.label}
              </button>
            ))}

            {/* Separator if there are custom frameworks */}
            {customFrameworks.length > 0 && (
              <div className="flex items-center px-1">
                <div className="h-5 w-px bg-gray-300 dark:bg-gray-600" />
              </div>
            )}

            {/* Custom framework tabs */}
            {customFrameworks.map((cf) => (
              <div key={cf.id} className="group relative flex items-center">
                <button
                  type="button"
                  onClick={() => handleCustomTabChange(cf.id)}
                  className={`whitespace-nowrap border-b-2 px-1 py-3 pr-6 text-sm font-medium transition-colors ${
                    activeTab.type === "custom" && activeTab.id === cf.id
                      ? "border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:border-gray-600 dark:hover:text-gray-300"
                  }`}
                >
                  {cf.name}
                </button>
                {isAdmin && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteCustomFramework(cf.id);
                    }}
                    className="absolute right-0 top-1/2 -translate-y-1/2 rounded p-0.5 text-gray-400 opacity-0 transition-opacity hover:text-red-500 group-hover:opacity-100 dark:text-gray-500 dark:hover:text-red-400"
                    title="Delete framework"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </nav>
        </div>

        {/* Error state */}
        {error && (
          <ErrorState
            message={error}
            onRetry={() => {
              if (activeTab.type === "builtin") {
                fetchControls(activeTab.key);
              } else {
                fetchCustomCompliance(activeTab.id);
              }
            }}
          />
        )}

        {/* Framework progress bar */}
        {!error && !currentLoading && currentControlCount > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {activeLabel}
                </h2>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {activeDescription}
                </p>
                <div className="mt-1 flex items-center gap-3">
                  <span className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
                    <span className="h-2 w-2 rounded-full bg-green-500" />
                    {currentSummary.passing} passing
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
                    <span className="h-2 w-2 rounded-full bg-red-500" />
                    {currentSummary.failing} failing
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
                    <span className="h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600" />
                    {currentSummary.total -
                      currentSummary.passing -
                      currentSummary.failing}{" "}
                    no data
                  </span>
                </div>
              </div>
              <span
                className={`text-3xl font-bold ${
                  currentProgressPct >= 80
                    ? "text-green-600"
                    : currentProgressPct >= 50
                      ? "text-amber-600"
                      : "text-red-600"
                }`}
              >
                {currentProgressPct}%
              </span>
            </div>
            <div className="mt-4 h-4 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className={`h-full rounded-full transition-all ${
                  currentProgressPct >= 80
                    ? "bg-green-500"
                    : currentProgressPct >= 50
                      ? "bg-amber-500"
                      : "bg-red-500"
                }`}
                style={{ width: `${currentProgressPct}%` }}
              />
            </div>
          </div>
        )}

        {/* Compliance trend chart (only for built-in frameworks) */}
        {!error && !isLoading && activeTab.type === "builtin" && (
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-900/30">
                  <TrendingUp className="h-5 w-5 text-indigo-500" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                    Compliance Trend
                  </h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {activeLabel} score over time
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {TREND_PERIODS.map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setTrendPeriod(p.value)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      trendPeriod === p.value
                        ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                        : "text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-4">
              {trendLoading ? (
                <div className="flex h-[280px] items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" />
                </div>
              ) : (
                <ComplianceTrendChart
                  data={trendData}
                  framework={TREND_FRAMEWORK_MAP[activeTab.key]}
                  period={trendPeriod}
                />
              )}
            </div>
          </div>
        )}

        {/* Filters */}
        {!error && (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label
                htmlFor="severity-filter"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Severity:
              </label>
              <select
                id="severity-filter"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
              >
                <option value="all">All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label
                htmlFor="search-input"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Search:
              </label>
              <input
                id="search-input"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter by name or code..."
                className="w-64 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:placeholder:text-gray-500"
              />
            </div>
          </div>
        )}

        {/* Controls list -- built-in frameworks */}
        {!error && activeTab.type === "builtin" && (
          <div className="space-y-4">
            {isLoading ? (
              <div className="flex h-64 items-center justify-center rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
              </div>
            ) : filteredControls.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <p className="text-lg font-medium text-gray-400">
                  No controls found
                </p>
                <p className="mt-1 text-sm text-gray-400">
                  {controls.length === 0
                    ? "Run a scan to evaluate your compliance posture."
                    : "Try adjusting your filters."}
                </p>
              </div>
            ) : (
              controlGroups.map((group) => (
                <div
                  key={group.key}
                  className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
                >
                  {/* Group header (only for SOC2/NIST/ISO) */}
                  {group.label && (
                    <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-800/80">
                      <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                        {group.label}
                      </h3>
                      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                        {group.controls.length} control
                        {group.controls.length !== 1 ? "s" : ""}
                      </p>
                    </div>
                  )}
                  <div className="divide-y divide-gray-100 dark:divide-gray-700">
                    {group.controls.map((control) => renderControlRow(control))}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Controls list -- custom frameworks */}
        {!error && activeTab.type === "custom" && (
          <div className="space-y-4">
            {customLoading ? (
              <div className="flex h-64 items-center justify-center rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
              </div>
            ) : filteredCustomControls.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <p className="text-lg font-medium text-gray-400">
                  No controls found
                </p>
                <p className="mt-1 text-sm text-gray-400">
                  {customCompliance?.total_controls === 0
                    ? "This framework has no controls mapped."
                    : "Try adjusting your filters."}
                </p>
              </div>
            ) : (
              customGroups.map((group) => (
                <div
                  key={group.key}
                  className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
                >
                  {/* Group header */}
                  {group.label && group.label !== "Ungrouped" && (
                    <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-800/80">
                      <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                        {group.label}
                      </h3>
                      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                        {group.items.length} control
                        {group.items.length !== 1 ? "s" : ""}
                      </p>
                    </div>
                  )}
                  <div className="divide-y divide-gray-100 dark:divide-gray-700">
                    {group.items.map((item) => renderCustomControlRow(item))}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Framework builder modal */}
      {showBuilder && (
        <FrameworkBuilderModal
          onClose={() => setShowBuilder(false)}
          onCreated={handleFrameworkCreated}
        />
      )}
    </AppShell>
  );
}
