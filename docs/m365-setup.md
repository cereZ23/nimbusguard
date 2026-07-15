# Connecting Microsoft 365

NimbusGuard assesses a Microsoft 365 tenant read-only through an **Entra app
registration** using the client-credentials flow (no user interaction, no
mailbox access). One app registration covers all four workloads: identity
(Entra), Exchange Online, SharePoint/OneDrive, and Teams.

## 1. Create the app registration

1. Entra admin center → **Identity → Applications → App registrations → New
   registration**.
2. Name it (e.g. `NimbusGuard CSPM`), single tenant, no redirect URI.
3. Note the **Application (client) ID** and **Directory (tenant) ID**.
4. **Certificates & secrets → New client secret** — note the secret value.

## 2. Grant Microsoft Graph application permissions

App registration → **API permissions → Add a permission → Microsoft Graph →
Application permissions**, then add:

| Permission                          | Used for                                             | Required?                     |
| ----------------------------------- | ---------------------------------------------------- | ----------------------------- |
| `Organization.Read.All`             | Tenant baseline (`/organization`, licenses)          | **Yes — connection fails without it** |
| `Directory.Read.All`                | Users, directory roles, domains, guest counts        | Identity checks               |
| `Policy.Read.All`                   | Conditional Access, security defaults, authorization & auth-method policies | Identity checks |
| `Reports.Read.All`                  | MFA registration coverage                            | Identity checks               |
| `SharePointTenantSettings.Read.All` | SharePoint/OneDrive tenant settings                  | SharePoint workload           |
| `SecurityEvents.Read.All`           | Microsoft Secure Score                               | Optional enrichment           |
| `TeamworkAppSettings.Read.All`      | Teams app settings                                   | Teams workload                |

Finish with **Grant admin consent**.

## 3. Enable Exchange Online collection

Exchange / Defender-for-Office settings are not available in Graph. Two
extra steps:

1. **API permissions → Add a permission → APIs my organization uses →
   Office 365 Exchange Online → Application permissions →
   `Exchange.ManageAsApp`** → grant admin consent.
2. Assign the app's service principal the **Global Reader** directory role
   (Entra admin center → Roles & admins → Global Reader → Add assignment →
   select the app). `Exchange Administrator` also works but grants write
   ability NimbusGuard never uses — prefer Global Reader.

NimbusGuard only ever invokes read (`Get-*`) cmdlets against the Exchange
admin endpoint; write cmdlets are rejected client-side.

## 4. Connect in NimbusGuard

Onboarding (or **Settings → Cloud Accounts → Add Account**) → provider
**Microsoft 365** → enter the tenant ID, client ID, and client secret →
**Test Connection**.

The connection test probes one endpoint per workload and reports exactly
which permissions are missing, e.g.:

> Connected to tenant Contoso. 3 of 4 workloads accessible.
> ⚠ Exchange Online & Defender checks unavailable: add the
> 'Exchange.ManageAsApp' application permission and assign the app the
> 'Global Reader' directory role.

You can connect with a partial permission set — checks whose data was not
collected are **skipped** (they never produce false findings) and the scan
records which workloads were covered.

## What gets assessed

83 controls mapped to the CIS Microsoft 365 Foundations Benchmark: 43
automated across the four workloads, 40 catalogued as manual (no app-only
API — e.g. Teams meeting policies, Purview DLP, Fabric settings). See
[CONTROLS.md](CONTROLS.md#microsoft-365-coverage) for the full breakdown.
