# Security Controls Reference

NimbusGuard ships **222 security checks** out of the box, mapped to
**CIS Benchmarks** and enriched with priority metadata (severity ×
effort × exposure) that feeds the [Priority / Triage layer](../README.md#priority--triage-layer).

| Provider      | Evaluators | YAML controls | Resource types |
| ------------- | ---------- | ------------- | -------------- |
| Azure         | **159**    | 163           | 34             |
| AWS           | **20**     | 20            | 12             |
| Microsoft 365 | **43**     | 83            | 4              |
| **Total**     | **222**    | **266**       | **50**         |

> The YAML count is slightly higher than the evaluator count because a few
> Azure controls (e.g. `CIS-AZ-01`, `CIS-AZ-02` for tenant-level MFA) are
> defined in `control_mappings.yaml` but rely on data sources we have not
> yet shipped (Entra ID / Graph collector).

All controls live in
[`backend/app/config/control_mappings.yaml`](../backend/app/config/control_mappings.yaml)
and are seeded into the `controls` table via `app.services.seed_controls`.

---

## Azure coverage

### Subscription-level (10 checks)

Read from `microsoft.subscription/subscription` — a synthetic asset
populated by `azure/subscription_collector.py` on top of Defender pricings,
security contacts, auto-provisioning settings, and RBAC role assignments.

- Defender for Cloud **Standard plan** enabled per service
  (Servers, Storage, SQL, App Service, Containers, Key Vault) — 6 checks
- Security contact email configured
- Security contact alert notifications enabled
- Auto-provisioning of the Log Analytics monitoring agent
- Subscription **Owner** role assignment count ≤ 3

### Compute & containers

| Resource type                                | Checks | Highlights                                                                                                                                                                                          |
| -------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `microsoft.compute/virtualmachines`          | 12     | Managed disks, disk encryption, boot diagnostics, secure boot, Trusted Launch / Confidential VM, vTPM, managed identity, OS disk CMK, automatic OS patching, availability zones                     |
| `microsoft.compute/disks`                    | 2      | Encryption at rest, network access                                                                                                                                                                  |
| `microsoft.containerservice/managedclusters` | 12     | RBAC, network policy, private cluster, AAD integration, authorized IP ranges, managed identity, Azure Policy add-on, Workload Identity + OIDC, local accounts off, Azure RBAC, auto-upgrade channel |
| `microsoft.containerregistry/registries`     | 8      | Admin disabled, public access, anonymous pull, network default Deny, quarantine policy, content trust, retention policy, CMK encryption                                                             |
| `microsoft.batch/batchaccounts`              | 2      | Pool allocation mode, public network access                                                                                                                                                         |

### Storage & databases

| Resource type                               | Checks | Highlights                                                                                                                                                                  |
| ------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `microsoft.storage/storageaccounts`         | 15     | HTTPS-only, min TLS 1.2, public access, encryption, versioning, cross-tenant replication, default Entra ID OAuth auth, cross-tenant SAS off, standard DNS, private endpoint |
| `microsoft.sql/servers`                     | 4      | TDE, public access, AAD admin, auditing                                                                                                                                     |
| `microsoft.sql/servers/databases`           | 3      | Encryption, geo-redundant backup, long-term retention                                                                                                                       |
| `microsoft.dbforpostgresql/flexibleservers` | 6      | SSL enforcement, log checkpoints, public access off, min TLS 1.2, geo-redundant backup, retention ≥ 7 days                                                                  |
| `microsoft.dbformysql/flexibleservers`      | 5      | SSL, public access, min TLS 1.2, geo-redundant backup, retention ≥ 7 days                                                                                                   |
| `microsoft.documentdb/databaseaccounts`     | 7      | Public access, VNet filter, CMK, automatic failover, continuous backup, periodic retention, multi-region write                                                              |
| `microsoft.cache/redis`                     | 3      | Non-SSL ports off, min TLS version, public access                                                                                                                           |
| `microsoft.recoveryservices/vaults`         | 5      | Geo-redundant storage, soft delete, cross-region restore, public access off, immutability                                                                                   |

### Web & identity

| Resource type                             | Checks | Highlights                                                                                                                                                                                          |
| ----------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `microsoft.web/sites`                     | 17     | HTTPS-only, min TLS 1.2, min TLS cipher suite, FTP off, managed identity, client cert, HTTP/2, remote debug off, CORS no wildcard, health check path, auto-heal, IP restrictions, public access off |
| `microsoft.web/serverfarms`               | 4      | Not on Free/Shared tier, zone redundancy, multiple workers for HA, per-site scaling                                                                                                                 |
| `microsoft.keyvault/vaults`               | 6      | Purge protection, soft delete, RBAC authz, public access, network rule default Deny, diagnostic setting                                                                                             |
| `microsoft.keyvault/vaults/keys`          | 1      | Expiration date set                                                                                                                                                                                 |
| `microsoft.keyvault/vaults/secrets`       | 1      | Expiration date set                                                                                                                                                                                 |
| `microsoft.keyvault/vaults/certificates`  | 1      | Expiration date set                                                                                                                                                                                 |
| `microsoft.authorization/roledefinitions` | 1      | Custom roles no wildcard permissions                                                                                                                                                                |

### Networking

| Resource type                              | Checks | Highlights                                                                                                         |
| ------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------ |
| `microsoft.network/networksecuritygroups`  | 7      | SSH/RDP restricted, flow logs, SMB/NetBIOS/WinRM ports, database ports, wildcard any-port rule, diagnostic setting |
| `microsoft.network/publicipaddresses`      | 3      | DDoS protection, Standard SKU (not deprecated Basic), not orphaned                                                 |
| `microsoft.network/azurefirewalls`         | 1      | Threat intelligence in Deny mode                                                                                   |
| `microsoft.network/applicationgateways`    | 3      | WAF enabled, WAF mode, diagnostic setting                                                                          |
| `microsoft.network/frontdoors`             | 3      | HTTPS only, WAF policy attached, diagnostic setting                                                                |
| `microsoft.network/virtualnetworks`        | 1      | DDoS protection standard                                                                                           |
| `microsoft.network/virtualnetworkgateways` | 1      | SKU not deprecated Basic                                                                                           |
| `microsoft.network/networkwatchers`        | 1      | Enabled in the region                                                                                              |
| `microsoft.network/networkinterfaces`      | 2      | IP forwarding disabled, accelerated networking                                                                     |

### Observability

| Resource type                              | Checks | Highlights                                                                                     |
| ------------------------------------------ | ------ | ---------------------------------------------------------------------------------------------- |
| `microsoft.operationalinsights/workspaces` | 6      | Retention ≥ 90d, CMK encryption, daily quota, public access off (query + ingestion), RBAC-only |
| `microsoft.insights/activitylogalerts`     | 1      | Alert on critical operations                                                                   |
| `microsoft.servicebus/namespaces`          | 3      | Min TLS 1.2, public access, diagnostic setting                                                 |
| `microsoft.eventhub/namespaces`            | 2      | Encryption, public access                                                                      |

### Diagnostic settings sweep (10 checks)

A dedicated sprint added a **cross-resource** diagnostic settings sweep —
one check per critical resource type that verifies at least one
`microsoft.insights/diagnosticsettings` target is configured
(Log Analytics, storage account, or Event Hub). Covered types:
SQL databases, Key Vaults, Web Apps, VMs, Cosmos DB, AKS clusters,
Application Gateways, Front Doors, Service Bus namespaces, NSGs.

These checks are **counted inside the per-resource-type tables above**
(for example, `microsoft.web/sites` diagnostic setting is part of its 17
checks). The sweep is implemented as individual `@check` functions, not
as a generic framework, to keep evaluator logic transparent and debuggable.

---

## AWS coverage

| Resource type             | Checks | Highlights                                                  |
| ------------------------- | ------ | ----------------------------------------------------------- |
| `aws.s3.bucket`           | 4      | Public access block, encryption, versioning, access logging |
| `aws.ec2.instance`        | 2      | IMDSv2 enforced, no public IP                               |
| `aws.ec2.security-group`  | 2      | No 0.0.0.0/0 on sensitive ports, no default SG rules        |
| `aws.ec2.volume`          | 1      | Encryption at rest                                          |
| `aws.ec2.vpc`             | 1      | VPC flow logs enabled                                       |
| `aws.rds.instance`        | 3      | Encryption, public access, multi-AZ                         |
| `aws.iam.user`            | 2      | MFA enabled, no access keys older than 90 days              |
| `aws.iam.password-policy` | 1      | Strong account password policy                              |
| `aws.iam.account-summary` | 1      | Root account MFA                                            |
| `aws.cloudtrail.trail`    | 1      | Multi-region trail enabled                                  |
| `aws.guardduty.detector`  | 1      | GuardDuty enabled in region                                 |
| `aws.lambda.function`     | 1      | Runtime not deprecated                                      |

---

## Microsoft 365 coverage

Mapped to the **CIS Microsoft 365 Foundations Benchmark** — codes mirror the
benchmark's section numbering (`CIS-M365-<section>.<sub>.<n>`), and the
catalogue is seeded under `framework: cis-m365` (its own tab on the
Compliance page).

The M365 collector (`backend/app/services/m365/`) authenticates with an
Entra app registration (client-credentials) and creates **four synthetic
assets**, one per workload:

| Resource type            | Data source                     | Automated checks | Highlights                                                                                                                                  |
| ------------------------ | ------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `microsoft365/tenant`    | Microsoft Graph                 | 16               | Global admin count, security defaults / Conditional Access MFA + legacy-auth block, MFA registration coverage, user defaults (app registration, consent, tenant/group creation), guest restrictions, password expiry, weak auth methods |
| `microsoft365/exchange`  | Exchange admin API (see below)  | 19               | Mailbox + unified audit, external forwarding blocked, transport-rule whitelisting, modern auth, MailTips, OWA storage providers, Safe Links / Safe Attachments (incl. SPO/Teams), anti-phishing, anti-malware file filter, DKIM, spam-filter allow lists |
| `microsoft365/sharepoint`| Graph `/admin/sharepoint/settings` | 7             | Legacy auth, external-sharing capability, invited-account matching, domain restriction, guest re-sharing, unmanaged sync, idle session sign-out |
| `microsoft365/teams`     | Graph `/teamwork/teamsAppSettings` | 1             | Resource-specific consent for Teams apps                                                                                                    |

### Manual controls

40 catalogued controls carry `automation: manual` — their settings have **no
app-only API** (Teams meeting/messaging/federation policies via CsTeams*
PowerShell, Purview DLP / sensitivity labels, Fabric tenant settings,
SPF/DMARC DNS records, PIM / access reviews, customer lockbox, and several
admin-center toggles). They appear in the catalogue and compliance PDF with
a **Manual** badge but never produce findings and are excluded from
compliance scores.

### Exchange admin API caveat

Exchange Online and Defender-for-Office configuration is not exposed through
Microsoft Graph. NimbusGuard calls the Exchange admin REST endpoint that the
official `ExchangeOnlineManagement` PowerShell module uses
(`POST https://outlook.office365.com/adminapi/beta/{tenant}/InvokeCommand`)
— the same approach used by Prowler, Monkey365, and ScubaGear. It requires
the **`Exchange.ManageAsApp`** application permission plus a **Global
Reader** directory-role assignment on the service principal, and the client
allowlists `Get-*` cmdlets only. If the role is missing, Exchange checks are
**skipped** (never failed) and the connection test reports the gap.

Setup walkthrough: [docs/m365-setup.md](m365-setup.md).

---

## Priority metadata

Every control in `control_mappings.yaml` can carry four extra fields
consumed by the Priority / Triage layer
([design doc](../backend/app/services/priority.py)):

```yaml
- code: CIS-AZ-85
  name: App Service Plan not on Free/Shared tier
  severity: medium # high / medium / low
  effort: quick # quick / moderate / refactor
  exposure: internet # internet / internal / none
  remediation_group: upgrade_appservice_plan_tier
  remediation_action: >
    Upgrade each App Service Plan off the Free/Shared tier so that
    production apps get SLA, zone redundancy, and auto-scaling.
```

When `effort` / `exposure` are omitted, the evaluator falls back to
heuristics defined in `priority.py`:

- **Effort** is inferred from keywords in the control name
  (`"enabled"` / `"disabled"` → `quick`; `"CMK"` / `"private endpoint"` / `"customer-managed"` → `refactor`; everything else → `moderate`).
- **Exposure** is inferred from the resource type
  (`microsoft.web/sites`, `microsoft.storage/storageaccounts`, any SQL /
  CosmosDB / DB flex server with a public endpoint → `internet`;
  `microsoft.keyvault/vaults`, AKS, Log Analytics → `internal`;
  everything else → `none`).

`remediation_group` is shared by controls with the **same underlying fix**
so the dashboard can present _"Enable Defender for Cloud"_ once and link to
all six findings it resolves. 19 groups are currently defined, covering
62 of the 179 evaluators — the rest default to single-control groups.

---

## Framework mappings

Each control is annotated with equivalent references in other frameworks:

```yaml
framework_mappings:
  soc2:
    - CC6.1
    - CC6.6
  nist:
    - SC-8
    - SC-28
  iso27001:
    - A.8.24
    - A.8.26
```

These mappings feed `/api/v1/compliance` (framework-view rollup) and the
PDF evidence pack's compliance matrix.

---

## Adding new controls

See [CONTRIBUTING.md](CONTRIBUTING.md#adding-new-security-checks) for the
step-by-step guide — write check + register + yaml entry + tests + bump
registry count. Average time to add a new check is ~10 minutes.
