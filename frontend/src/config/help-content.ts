export const HELP_CONTENT = {
  dashboard: {
    secureScore:
      "Your overall security posture score (0-100%). Based on the ratio of passing to total security checks across all connected cloud accounts.",
    findings:
      "Security issues detected in your cloud resources. Higher severity findings require more urgent attention.",
    assets:
      "Cloud resources discovered during scans. Includes VMs, storage accounts, databases, and other infrastructure.",
    trend:
      "Shows how your security findings have changed over time. A downward trend indicates improving security posture.",
    highSeverity:
      "Count of findings rated High severity. These require immediate attention and remediation within 24 hours.",
    kpiScore:
      "Percentage of security controls currently passing. Higher is better — aim for 80% or above.",
  },
  findings: {
    severity:
      "Critical: immediate action required. High: address within 24h. Medium: address within 1 week. Low: address during next maintenance window.",
    status:
      "Open: active issue. In Progress: being worked on. Waived: accepted risk with justification. Resolved: issue has been fixed.",
    bulkActions:
      "Select multiple findings to perform batch operations like requesting waivers for accepted risks.",
    waiver:
      "A waiver acknowledges an accepted risk with a documented justification. Waivers require admin approval.",
  },
  assets: {
    resourceType:
      "The Azure resource type (e.g., Storage Account, Virtual Machine, Key Vault).",
    lastSeen:
      "When this resource was last detected during a scan. Resources not seen in recent scans may have been deleted.",
    region:
      "The Azure region where this resource is deployed. Resources in different regions may have different compliance requirements.",
  },
  compliance: {
    framework:
      "Compliance frameworks map your security controls to regulatory requirements. Select a framework to see your compliance posture.",
    score:
      "Percentage of controls passing for this framework. 80%+ is generally considered a good baseline.",
    customFramework:
      "Create your own compliance framework by selecting which controls to include and organizing them into groups.",
    control:
      "A security control is a specific security requirement that is checked against your cloud resources.",
  },
  settings: {
    apiKeys:
      "API keys allow programmatic access to the CSPM API for CI/CD integration and automation.",
    webhooks:
      "Webhooks send HTTP POST notifications to your endpoints when security events occur.",
    mfa: "Two-factor authentication adds an extra layer of security to your account using time-based codes.",
    cloudAccount:
      "A cloud account connects CSPM to your Azure subscription. CSPM requires Reader and Security Reader roles.",
  },
} as const;
