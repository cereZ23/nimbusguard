"use client";

import { useState } from "react";
import { Lightbulb, Code, Terminal, Sparkles } from "lucide-react";
import CopyButton from "./copy-button";

export interface RemediationData {
  control_code: string;
  control_name: string;
  description: string | null;
  remediation_hint: string | null;
  snippets: {
    terraform: string | null;
    bicep: string | null;
    azure_cli: string | null;
  };
  // True when the snippet was rendered with the finding's asset values
  // (subscription, resource group, resource name). Drives the "Filled
  // for <asset>" badge.
  filled_for_asset?: boolean;
  // The asset display name the snippet was filled for. Only set when
  // `filled_for_asset` is true.
  asset_name?: string | null;
}

// Regex to detect remaining @@marker@@ placeholders in a snippet — used
// to warn the user that they still need to fill in some values manually.
const UNFILLED_MARKER_RE = /@@[a-z_]+@@/;

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

interface RemediationPanelProps {
  remediation: RemediationData | null;
  fallbackHint?: string;
}

function RemediationPanel({
  remediation,
  fallbackHint,
}: RemediationPanelProps) {
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
  const hasUnfilledMarkers = activeSnippet
    ? UNFILLED_MARKER_RE.test(activeSnippet)
    : false;
  const filledForAsset = Boolean(
    remediation?.filled_for_asset && remediation?.asset_name,
  );

  // If no remediation data at all, fall back to hint
  if (!remediation && !fallbackHint) return null;

  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50 shadow-sm dark:border-emerald-800 dark:bg-emerald-900/20">
      {/* Header */}
      <div className="px-5 pt-5 pb-3">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-emerald-800 dark:text-emerald-300">
            <Lightbulb className="h-4 w-4 flex-shrink-0" />
            Remediation Guidance
          </h2>
          {filledForAsset && (
            <span
              title="Snippet pre-filled with this resource's subscription, resource group, and name"
              className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white shadow-sm dark:bg-emerald-500"
            >
              <Sparkles className="h-3 w-3" />
              Filled for {remediation?.asset_name}
            </span>
          )}
        </div>
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
              {hasUnfilledMarkers && (
                <p className="border-t border-gray-700 px-3 py-2 text-[11px] text-amber-300">
                  Some values marked <code>@@name@@</code> still need to be
                  filled in manually (e.g. workspace ID, Key Vault key name).
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default RemediationPanel;
