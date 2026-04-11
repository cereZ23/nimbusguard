# Changelog

All notable changes to NimbusGuard are documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Each entry references the git commit SHA that shipped it.

## [Unreleased]

## 2026-04-11 — Priority / Triage layer

### Added

- **Priority / Triage layer (P0..P3)** — commit `c9ebd15`.
  Every failing finding is automatically bucketed by a transparent
  3x3 matrix of severity × effort, with a one-tier bump when the finding
  is internet-exposed (capped at P0). The formula is yaml-driven and
  customisable per tenant — no proprietary ML, no black-box scoring.
- Dashboard "Priority Overview" card with 4 clickable counters
  (P0/P1/P2/P3) + segmented Secure Score projection bar showing
  _current score → after fixing P0 → after fixing P0+P1_.
- Dashboard "Top actions to fix this week" card listing the top 5
  remediation groups with affected-finding count and click-through to
  the filtered findings list.
- Findings page gains a new **Priority** column as the first data
  column, default sort is now `sort_by=priority`, and new filter
  dropdowns for Priority and Remediation Group.
- Backend `GET /api/v1/dashboard/priority-summary` endpoint returning
  counts, top remediation groups, and Secure Score projections.
- `GET /api/v1/findings` extended with `priority` and `remediation_group`
  filters plus `sort_by=priority` (orders by `priority_score DESC NULLS LAST`).
- New `app/services/priority.py` module with `compute_priority()`,
  `compute_priority_score()`, `default_effort()`, `default_exposure()`
  and `project_secure_score_after_fixing()` helpers, all covered by
  65 unit tests.
- Alembic migration `f6a7b8c9d0e1` adds `priority` + `priority_score`
  columns on `findings` and `effort` + `exposure` + `remediation_group`
  - `remediation_action` columns on `controls`, with indexes on
    `findings.priority` and `findings.priority_score DESC`.
- 62 controls in `control_mappings.yaml` annotated with explicit
  `remediation_group` (19 distinct groups), 21 with explicit
  `effort` / `exposure` overrides.

### Live validation on the IFO production tenant

Rescanning the IFO subscription (6 real Azure assets + 1 synthetic
subscription asset = 7 assets, 86 evaluations) produced this priority
distribution:

| Bucket     | Count  | Meaning         |
| ---------- | ------ | --------------- |
| **P0**     | **25** | Fix now         |
| **P1**     | **29** | Fix this week   |
| **P2**     | 8      | Fix this sprint |
| **P3**     | 3      | Best practice   |
| Total fail | **65** |                 |
| Pass       | 21     |                 |

Current Secure Score: **24.4%** → projected **53.5%** after fixing P0,
**87.2%** after fixing P0+P1. This matches the predicted numbers from
the pre-sprint design doc.

## 2026-04-10 — Azure coverage expansion (+79 controls)

Nearly doubled Azure check coverage in one day across nine
self-contained sprints. All shipped via the CD pipeline. Each sprint
was validated against 1000+ unit tests locally before push.

### Sprint 1 — Depth expansion on existing resource types (CIS-AZ-85..103)

**Commits:** `be168dd`, `55a9dc3`.
19 new checks across four modules:

- **App Service Plans** — new module `serverfarms.py` (4 checks):
  not on Free/Shared tier, zone redundancy, multiple workers for HA,
  per-site scaling on multi-site plans.
- **Web Apps** — `webapp.py` extended from 10 to 16 checks:
  CORS without wildcard, health check path, auto-heal rules,
  minimum TLS cipher suite, public access off with private endpoint,
  IP security restrictions.
- **Storage Accounts** — `storage.py` extended from 10 to 15 checks:
  cross-tenant replication disabled, default Entra ID OAuth auth,
  cross-tenant SAS delegation off, public access off with private endpoint,
  standard DNS endpoint type.
- **Log Analytics Workspaces** — `log_analytics.py` extended from 2
  to 6 checks: daily ingestion quota, public access for query/ingestion
  disabled, RBAC-only log access.

### Sprint 2 — Subscription-level state collector (CIS-AZ-104..113)

**Commit:** `d9f673d`.
New `azure/subscription_collector.py` introduces a second Azure data
source beyond Resource Graph: Security Center pricings API, security
contacts API, auto-provisioning settings API, and RBAC role assignments
API. The collector creates a synthetic Asset with
`resource_type="microsoft.subscription/subscription"` so the existing
evaluator framework picks it up with no special-case logic.

10 new checks answer the single most common CSPM buyer question —
_"Do you tell me whether Defender for Cloud is turned on?"_:
Defender plans per service (Servers, Storage, SQL, App Service,
Containers, Key Vault), security contact email + alert notifications,
auto-provisioning of the monitoring agent, subscription Owner role
assignment count ≤ 3.

No additional Azure permissions required — the existing `Reader` +
`Security Reader` roles grant read access to all these APIs.

### Sprint 3 — Backup & DR posture (CIS-AZ-114..121)

**Commit:** `b49b012`.
8 new checks across three resource types:

- **Recovery Services Vaults** (5 checks): geo-redundant storage,
  soft delete, cross-region restore, public access off, immutability.
- **SQL databases** (1 check): backup storage redundancy in `{Geo, GeoZone}`.
- **Cosmos DB** (2 checks): continuous backup enabled, periodic
  retention ≥ 7 days.

### Sprint 4 — Network exposure hardening (CIS-AZ-122..127)

**Commit:** `81d40fb`.
6 checks complementing the existing SSH/RDP-only NSG controls:

- NSG no SMB/NetBIOS/WinRM from the internet
- NSG no database ports (SQL/MySQL/Postgres/Mongo/Redis/Elasticsearch/CouchDB) from the internet
- NSG no wildcard any-port rule from the internet
- Public IP on Standard SKU (not deprecated Basic)
- Public IP not orphaned
- Azure Firewall threat-intelligence in Deny mode

Adds `microsoft.network/azurefirewalls` as a new covered resource type.

### Sprint 5 — AKS deep hardening (CIS-AZ-128..134)

**Commit:** `f485c5f`.
7 new checks on `microsoft.containerservice/managedclusters`:
API server authorized IP ranges (skipped for private clusters),
managed identity vs service principal, Azure Policy add-on enabled,
Workload Identity + OIDC issuer, local admin accounts disabled,
Azure RBAC for Kubernetes authorisation, auto-upgrade channel.

### Sprint 6 — ACR supply chain (CIS-AZ-135..140)

**Commit:** `f485c5f`.
6 checks on `microsoft.containerregistry/registries`:
anonymous pull disabled, network rule default Deny, quarantine policy,
content trust / image signing, retention policy, CMK encryption.

### Sprint 7 — PostgreSQL / MySQL flex hardening (CIS-AZ-141..146)

**Commit:** `f485c5f`.
6 checks split across `microsoft.dbforpostgresql/flexibleservers`
and `microsoft.dbformysql/flexibleservers`:
PG public access off, PG min TLS 1.2, PG geo-redundant backup,
PG backup retention ≥ 7d, MySQL geo-redundant backup,
MySQL backup retention ≥ 7d.

### Sprint 8 — VM deep hardening (CIS-AZ-147..153)

**Commit:** `f4867d0`.
7 new checks on `microsoft.compute/virtualmachines` complementing
the baseline managed disks / disk encryption / boot diagnostics /
secure boot checks already in `compute.py`:
Trusted Launch or Confidential VM security type, vTPM enabled,
managed identity assigned, boot diagnostics on managed storage,
OS disk CMK encryption, automatic OS patching, VM availability
(zones or availability set).

### Sprint 9 — Diagnostic settings sweep (CIS-AZ-154..163)

**Commit:** `f4867d0`.
New collector method `_collect_diagnostic_settings()` in
`azure/collector.py` queries `microsoft.insights/diagnosticsettings`
via Resource Graph and patches each target asset's `raw_properties`
with a list of diagnostic setting summaries. Plus 10 new evaluator
checks verifying that each critical resource type has at least one
diagnostic setting pointing to Log Analytics, storage or Event Hub:
SQL databases (CIS-AZ-154), Key Vaults (155), Web Apps (156),
VMs (157), Cosmos DB (158), AKS clusters (159), Application Gateways
(160), Front Doors (161), Service Bus namespaces (162), NSGs (163).

### Totals after the expansion

|                                | Before | After    |
| ------------------------------ | ------ | -------- |
| Azure CIS-Lite controls (yaml) | 84     | **163**  |
| Azure evaluators registered    | 80     | **159**  |
| Total registry (Azure + AWS)   | 100    | **179**  |
| Azure resource types covered   | 30     | **35**   |
| Backend tests                  | 815    | **1273** |

## 2026-04-10 — Dedicated `/scans` page

**Commit:** `37fad6b`.

- Moved the scan trigger out of `Settings → Accounts` (buried, 4
  clicks from home) into a first-class top-level page at `/scans`
  (1 click from the sidebar).
- Full scan history with filters by cloud account and status
  (pending / running / completed / failed).
- Per-row breakdown: duration, controls evaluated, pass/fail/total
  findings, scan type.
- **Auto-polls every 5 seconds** while any visible scan is running,
  giving live progress updates without manual refresh.
- New backend endpoint `GET /api/v1/scans` with pagination, tenant
  isolation, and batched findings aggregation (no N+1 queries).
- The Settings → Accounts page retains a per-account shortcut: the
  `Scans` button deep-links to `/scans?cloud_account_id=<id>`.

## 2026-04-10 — CI/CD hardening

**Commit:** `55f7427`.

- Backend `Dockerfile` runtime stage now runs
  `apt-get update && apt-get -y --no-install-recommends upgrade`
  to pick up the latest Debian security patches at build time. This
  closes the openssl CVE-2026-28390 family on every rebuild.
- New `.trivyignore` at the repo root documents the two unpatchable
  HIGH CVEs (ncurses CVE-2025-69720 and systemd CVE-2026-29111) with
  a rationale for why they are not exploitable in the container — the
  container runs `uvicorn` as PID 1 with no interactive CLI tools and
  no systemd, so both exploit paths are unreachable.
- `.github/workflows/ci.yml` points the `trivy-action` step at the new
  `.trivyignore` file so the CI scan passes without blocking unrelated
  Debian base-layer findings.

Follow-up reminder: periodically re-check the two entries in
`.trivyignore` against Debian's security tracker and remove them as
upstream patches land.

## [Prior history]

Releases prior to commit `be168dd` (early April 2026 baseline) had:

- 84 Azure CIS-Lite controls across 30 resource types
- 20 AWS CIS controls
- Multi-tenant architecture with JWT + cookies + RBAC
- SSO/OIDC + MFA (TOTP + backup codes)
- PDF evidence export, Jira & Slack integrations, scheduled scans
- 815 backend tests passing

See the git log for the commit-level history.
