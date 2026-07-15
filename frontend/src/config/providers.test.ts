import { describe, it, expect } from "vitest";
import {
  PROVIDERS,
  PROVIDER_LIST,
  providerFromResourceType,
} from "@/config/providers";
import type { CloudProvider } from "@/types";

const ALL_SLUGS: CloudProvider[] = ["azure", "aws", "m365"];

describe("PROVIDERS registry", () => {
  it("contains all three providers with complete metadata", () => {
    for (const slug of ALL_SLUGS) {
      const config = PROVIDERS[slug];
      expect(config.slug).toBe(slug);
      expect(config.label.length).toBeGreaterThan(0);
      expect(config.shortLabel.length).toBeGreaterThan(0);
      expect(config.badgeClass.length).toBeGreaterThan(0);
      expect(config.color).toMatch(/^#[0-9a-fA-F]{6}$/);
      expect(config.accountIdLabel.length).toBeGreaterThan(0);
      expect(config.accountIdPlaceholder.length).toBeGreaterThan(0);
      expect(config.portalName.length).toBeGreaterThan(0);
    }
  });

  it("exposes provider-specific labels", () => {
    expect(PROVIDERS.azure.label).toBe("Microsoft Azure");
    expect(PROVIDERS.aws.label).toBe("Amazon Web Services");
    expect(PROVIDERS.m365.label).toBe("Microsoft 365");
    expect(PROVIDERS.azure.shortLabel).toBe("Azure");
    expect(PROVIDERS.aws.shortLabel).toBe("AWS");
    expect(PROVIDERS.m365.shortLabel).toBe("M365");
    expect(PROVIDERS.azure.accountIdLabel).toBe("Subscription ID");
    expect(PROVIDERS.aws.accountIdLabel).toBe("AWS Account ID");
    expect(PROVIDERS.m365.accountIdLabel).toBe("Entra Tenant ID");
  });

  it("lists all providers in PROVIDER_LIST", () => {
    expect(PROVIDER_LIST.map((p) => p.slug)).toEqual(ALL_SLUGS);
  });
});

describe("portalUrlForAsset", () => {
  it("builds an Azure portal deep link from provider_id", () => {
    const url = PROVIDERS.azure.portalUrlForAsset({
      provider_id: "/subscriptions/abc/resourceGroups/rg1",
      resource_type: "Microsoft.Compute/virtualMachines",
    });
    expect(url).toBe(
      "https://portal.azure.com/#@/resource/subscriptions/abc/resourceGroups/rg1",
    );
  });

  it("returns null for Azure assets without a provider_id", () => {
    expect(PROVIDERS.azure.portalUrlForAsset({ provider_id: null })).toBeNull();
    expect(PROVIDERS.azure.portalUrlForAsset({})).toBeNull();
  });

  it("returns null for AWS assets (no deep link)", () => {
    expect(
      PROVIDERS.aws.portalUrlForAsset({
        provider_id: "arn:aws:s3:::my-bucket",
        resource_type: "aws.s3.bucket",
      }),
    ).toBeNull();
  });

  it("maps m365 resource types to the right admin portals", () => {
    const cases: [string, string][] = [
      ["microsoft365/tenant", "https://entra.microsoft.com"],
      ["microsoft365/exchange", "https://admin.exchange.microsoft.com"],
      ["microsoft365/sharepoint", "https://admin.microsoft.com"],
      ["microsoft365/teams", "https://admin.teams.microsoft.com"],
    ];
    for (const [resourceType, expected] of cases) {
      expect(
        PROVIDERS.m365.portalUrlForAsset({ resource_type: resourceType }),
      ).toBe(expected);
    }
  });

  it("falls back to the Microsoft admin center for unknown m365 types", () => {
    expect(
      PROVIDERS.m365.portalUrlForAsset({ resource_type: "microsoft365/other" }),
    ).toBe("https://admin.microsoft.com");
    expect(PROVIDERS.m365.portalUrlForAsset({})).toBe(
      "https://admin.microsoft.com",
    );
  });
});

describe("providerFromResourceType", () => {
  it("derives m365 from the microsoft365/ prefix", () => {
    expect(providerFromResourceType("microsoft365/exchange")).toBe("m365");
  });

  it("derives aws from the aws. prefix", () => {
    expect(providerFromResourceType("aws.ec2.instance")).toBe("aws");
  });

  it("defaults to azure otherwise", () => {
    expect(
      providerFromResourceType("Microsoft.Compute/virtualMachines"),
    ).toBe("azure");
    expect(providerFromResourceType(null)).toBe("azure");
    expect(providerFromResourceType(undefined)).toBe("azure");
  });
});
