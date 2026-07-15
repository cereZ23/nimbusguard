import type { CloudProvider } from "@/types";

// ── Central cloud provider registry ─────────────────────────────────

export interface PortalAsset {
  provider_id?: string | null;
  resource_type?: string | null;
}

export interface ProviderConfig {
  slug: CloudProvider;
  label: string;
  shortLabel: string;
  /** Tailwind classes for the small provider badge/pill. */
  badgeClass: string;
  /** Brand hex color used in charts and graphs. */
  color: string;
  accountIdLabel: string;
  accountIdPlaceholder: string;
  /** Human name of the provider's management portal. */
  portalName: string;
  /** Deep link into the provider portal for an asset, or null if none. */
  portalUrlForAsset: (asset: PortalAsset) => string | null;
}

const M365_PORTAL_URLS: Record<string, string> = {
  "microsoft365/tenant": "https://entra.microsoft.com",
  "microsoft365/exchange": "https://admin.exchange.microsoft.com",
  "microsoft365/sharepoint": "https://admin.microsoft.com",
  "microsoft365/teams": "https://admin.teams.microsoft.com",
};

export const PROVIDERS: Record<CloudProvider, ProviderConfig> = {
  azure: {
    slug: "azure",
    label: "Microsoft Azure",
    shortLabel: "Azure",
    badgeClass:
      "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    color: "#0078d4",
    accountIdLabel: "Subscription ID",
    accountIdPlaceholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    portalName: "Azure Portal",
    portalUrlForAsset: (asset) =>
      asset.provider_id
        ? `https://portal.azure.com/#@/resource${asset.provider_id}`
        : null,
  },
  aws: {
    slug: "aws",
    label: "Amazon Web Services",
    shortLabel: "AWS",
    badgeClass:
      "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
    color: "#ff9900",
    accountIdLabel: "AWS Account ID",
    accountIdPlaceholder: "123456789012",
    portalName: "AWS Console",
    // No deep link into the AWS console today.
    portalUrlForAsset: () => null,
  },
  m365: {
    slug: "m365",
    label: "Microsoft 365",
    shortLabel: "M365",
    badgeClass:
      "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",
    color: "#0f7b6c",
    accountIdLabel: "Entra Tenant ID",
    accountIdPlaceholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    portalName: "Microsoft Admin Center",
    portalUrlForAsset: (asset) =>
      M365_PORTAL_URLS[asset.resource_type ?? ""] ??
      "https://admin.microsoft.com",
  },
};

export const PROVIDER_LIST: ProviderConfig[] = [
  PROVIDERS.azure,
  PROVIDERS.aws,
  PROVIDERS.m365,
];

/**
 * Derive the cloud provider from a resource type when the asset payload
 * carries no explicit provider field ("microsoft365/" -> m365,
 * "aws." -> aws, everything else is Azure).
 */
export function providerFromResourceType(
  resourceType?: string | null,
): CloudProvider {
  if (resourceType?.startsWith("microsoft365/")) return "m365";
  if (resourceType?.startsWith("aws.")) return "aws";
  return "azure";
}
