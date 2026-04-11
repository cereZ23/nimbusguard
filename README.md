<p align="center">
  <img src="https://img.shields.io/badge/NimbusGuard-Cloud%20Security-0ea5e9?style=for-the-badge&logo=icloud&logoColor=white" alt="NimbusGuard" />
</p>

<h1 align="center">NimbusGuard</h1>

<p align="center">
  <strong>Cloud Security Posture Management Platform</strong><br/>
  Continuous security assessment for Azure and AWS — built for MSSPs and security teams.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776ab?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js_14-000?logo=nextdotjs&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/PostgreSQL_16-4169e1?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Redis_7-dc382d?logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Celery-37814a?logo=celery&logoColor=white" alt="Celery" />
  <img src="https://img.shields.io/badge/tests-1273_passing-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License" />
  <br/>
  <a href="https://github.com/cereZ23/nimbusguard/actions"><img src="https://github.com/cereZ23/nimbusguard/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/code%20style-ruff-261230?logo=ruff&logoColor=d7ff64" alt="Ruff" />
  <img src="https://img.shields.io/badge/type%20checked-mypy-blue?logo=python&logoColor=white" alt="Type Checked" />
  <img src="https://img.shields.io/badge/security-CIS%20Benchmarks-00b4d8" alt="CIS Benchmarks" />
  <img src="https://img.shields.io/badge/coverage-84%25-brightgreen" alt="Coverage" />
  <img src="https://img.shields.io/badge/checks-162-0ea5e9" alt="Security Checks" />
  <img src="https://img.shields.io/badge/maintainability-A-brightgreen" alt="Maintainability" />
</p>

---

## What is NimbusGuard?

NimbusGuard is a **multi-tenant CSPM** (Cloud Security Posture Management) platform that continuously scans your cloud infrastructure, evaluates it against **162 security checks** mapped to CIS Benchmarks, and gives you a clear picture of your security posture — all from a single dashboard.

### Key Features

- **162 built-in security checks** across Azure (142 controls) and AWS (20 controls), mapped to CIS v3.0
- **Priority/Triage layer (P0..P3)** — every failing finding is automatically bucketed by severity + effort + exposure, so that your team fixes the right things first instead of drowning in a flat list of issues. Top-10 grouped remediation actions on the dashboard resolve multiple findings with a single fix
- **Secure Score projection** — the dashboard shows exactly how much your Secure Score would increase if you fixed the P0 bucket, or P0+P1, so the path from "23% now" to "62% after one week of fixes" is explicit
- **Multi-cloud support** — Azure today, AWS in progress, GCP on the roadmap
- **Dedicated Scans page** — first-class scan history with live updates, filters by account and status, per-scan findings breakdown (pass/fail/total)
- **Real-time Secure Score** — aggregated per-account and cross-cloud
- **Asset inventory** — full visibility into every cloud resource, searchable and filterable
- **Findings management** — prioritized by severity AND priority bucket, with remediation guidance and evidence
- **Bulk operations** — waive, comment, and manage findings at scale
- **PDF evidence packs** — export compliance reports with one click
- **Multi-tenant architecture** — designed for MSSPs managing multiple customers
- **SSO/OIDC integration** — Azure AD, Okta, Google Workspace, custom OIDC
- **MFA/TOTP** — two-factor authentication with backup codes
- **Custom RBAC** — granular roles and permissions beyond admin/viewer
- **Invitation system** — onboard team members with role-based invitations
- **Scheduled scans** — cron-based automated scanning via Celery Beat
- **Jira & Slack integration** — push findings to your workflow tools
- **API keys** — programmatic access for CI/CD pipelines
- **Dark/light mode** — because your SOC analysts work at night too

---

## What's new

### Recently shipped — April 2026

**🎯 Priority/Triage layer (P0..P3)** — commit `c9ebd15`

The single most strategic feature on the product. Transforms NimbusGuard from "Scanner" tier to "Advisor" tier by turning a flat list of findings into a ranked action plan that the user can work through top-down.

**How it works:**

Every failing finding is automatically assigned a priority bucket (`P0` / `P1` / `P2` / `P3`) computed from three transparent axes encoded in `control_mappings.yaml`:

| Axis         | Values                            | How it's set                                                                                                                        |
| ------------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Severity** | `high` / `medium` / `low`         | From the CIS benchmark definition (existing field)                                                                                  |
| **Effort**   | `quick` / `moderate` / `refactor` | Explicit in yaml or inferred from keywords in the control name (e.g. "CMK encryption" → refactor, "enabled" → quick)                |
| **Exposure** | `internet` / `internal` / `none`  | Explicit in yaml or inferred from the resource type (e.g. `microsoft.web/sites` → internet, `microsoft.keyvault/vaults` → internal) |

The formula is a 3×3 matrix bumped up one tier when the finding is internet-exposed. It is **entirely transparent** — no ML black box, no vendor lock-in, and 100% customisable per tenant via yaml overrides.

```
               quick      moderate    refactor
high:            P0          P1          P2
medium:          P1          P2          P3
low:             P2          P3          P3

+ internet exposure → bump up one tier (capped at P0)
```

**What the user sees:**

- **Dashboard "Priority Overview" card**: 4 large clickable counters (P0/P1/P2/P3) plus a segmented Secure Score projection bar showing _current score → after fixing P0 → after fixing P0+P1_ with the delta in points. Click any bucket to jump to `/findings?priority=P0&status=fail`.
- **Dashboard "Top actions to fix this week" card**: the top 5 remediation groups (e.g. _"Enable Microsoft Defender for Cloud Standard plan"_, _"Set minTlsVersion=1.2 on web apps"_) with the number of findings each action resolves. One click opens the filtered findings list so the team can work through the group as a unit.
- **Findings page**: new **Priority** column as the first data column, default sort is now by priority (P0 always at the top), new **Priority** filter dropdown and **Remediation Group** filter wired via URL params.

**Backend changes:**

- Alembic migration `f6a7b8c9d0e1` adds `priority` + `priority_score` to `findings` and `effort` + `exposure` + `remediation_group` + `remediation_action` to `controls`, with indexes on `priority` and `priority_score DESC`.
- New `app/services/priority.py` with `compute_priority()`, `compute_priority_score()` (0-255 stable intra-bucket sort), `default_effort()` / `default_exposure()` helpers, and `project_secure_score_after_fixing()`.
- Evaluator populates the priority on every failing finding during a scan.
- New `GET /api/v1/dashboard/priority-summary` endpoint returning counts, top remediation groups, and Secure Score projections.
- `GET /api/v1/findings` extended with `priority` and `remediation_group` filters and `sort_by=priority`.
- 62 controls annotated with explicit `remediation_group` in yaml (19 groups total) so that common fixes like "Enable Defender for Cloud", "Restrict storage public access", "Enforce managed identity" aggregate correctly.

**Why it matters (strategic positioning):**

Without triage, a tenant with 68 failing findings produces **noise**. The user opens the findings page, sees a flat list, closes it. With triage, the same tenant shows _"12 P0 items — fix now — +15% Secure Score after fixing"_ and _"Top action: Enable Defender for Cloud Standard → resolves 6 findings with one click"_. Same underlying data, entirely different user experience.

Competitors (Wiz, Prisma Cloud, Defender CSPM, Orca) use proprietary black-box ML scoring that the buyer can't inspect or customise. Open-source CSPMs (Prowler, Steampipe, CloudQuery, ScoutSuite) have no triage at all. A transparent, yaml-driven, customisable priority formula is a unique position on the market and is the feature that unlocks the "Advisor" pricing tier (~3-5x vs "Scanner").

---

Azure coverage nearly **doubled** in one day: **62 new CIS-Lite controls** (CIS-AZ-85..146), grouped in 7 self-contained sprints, all deployed via the CD pipeline. Every sprint is validated locally against 1000+ unit tests before being pushed to main.

**Numbers at a glance**

|                                | Before | After    |
| ------------------------------ | ------ | -------- |
| Azure CIS-Lite controls (yaml) | 84     | **146**  |
| Azure evaluators registered    | 80     | **142**  |
| Total registry (Azure + AWS)   | 100    | **162**  |
| Backend tests                  | 815    | **1273** |
| Azure resource types covered   | 30     | **35**   |

**Sprint 1 — Depth expansion on existing resource types** (CIS-AZ-85..103, commit `55a9dc3`)

19 new checks across four Azure service categories: App Service Plans (NEW module, `microsoft.web/serverfarms`, 4 checks), Web Apps (`microsoft.web/sites`, 10 → 16), Storage Accounts (`microsoft.storage/storageaccounts`, 10 → 15), Log Analytics Workspaces (`microsoft.operationalinsights/workspaces`, 2 → 6).

**Sprint 2 — Subscription-level state collector** (CIS-AZ-104..113, commit `d9f673d`)

New `azure/subscription_collector.py` adds a second Azure data source beyond Resource Graph, calling Security Center pricings, security contacts, auto-provisioning settings, and RBAC role assignments APIs. The collector creates a synthetic Asset with `resource_type="microsoft.subscription/subscription"` so the existing evaluator framework picks it up with no special-case logic. Ten new checks answer the single most common CSPM buyer question — _"Do you tell me whether Defender for Cloud is turned on?"_:

- Defender for Cloud plans per service (Servers, Storage, SQL, App Service, Containers, Key Vault)
- Security contact email + alert notifications configured
- Auto-provisioning of the monitoring agent enabled
- Subscription Owner role assignment count <= 3

No additional Azure permissions required — the existing `Reader` + `Security Reader` roles grant read access to all these APIs.

**Sprint 3 — Backup & disaster-recovery posture** (CIS-AZ-114..121, commit `b49b012`)

8 new checks across three resource types: Recovery Services Vaults (5 checks — geo-redundant storage, soft delete, cross-region restore, public access off, immutability), SQL databases (1 check — geo-redundant backup storage), Cosmos DB (2 checks — continuous backup, periodic retention ≥ 7 days).

**Sprint 4 — Network exposure hardening** (CIS-AZ-122..127, commit `81d40fb`)

6 new checks that complement the existing SSH/RDP-only NSG controls: NSG no SMB/NetBIOS/WinRM from the internet, NSG no database ports (SQL/MySQL/Postgres/Mongo/Redis/Elasticsearch) from the internet, NSG no wildcard any-port rule from the internet, Public IP on Standard SKU (not the deprecated Basic), Public IP not orphaned, Azure Firewall threat-intelligence in Deny mode. Adds `microsoft.network/azurefirewalls` as a NEW covered resource type.

**Sprint 5, 6, 7 — AKS / ACR / PG&MySQL deep hardening** (CIS-AZ-128..146, commit `f485c5f`)

19 new checks across three hardening areas, all reading properties already collected by the generic Resource Graph query:

- **AKS hardening** (7 checks): API server authorized IP ranges, managed identity vs service principal, Azure Policy add-on, Workload Identity + OIDC issuer, local admin accounts disabled, Azure RBAC for Kubernetes, auto-upgrade channel configured.
- **ACR supply chain** (6 checks): anonymous pull disabled, network rule default Deny, quarantine policy enabled, content trust / image signing enabled, retention policy enabled, customer-managed key encryption.
- **PG/MySQL flexible server hardening** (6 checks): Postgres public access off, Postgres min TLS 1.2, Postgres geo-redundant backup, Postgres backup retention ≥ 7d, MySQL geo-redundant backup, MySQL backup retention ≥ 7d.

**Sprint UX — Dedicated `/scans` page** (commit `37fad6b`)

- Moved the scan trigger out of `Settings → Accounts` (buried, 4 clicks from home) into a first-class top-level page at `/scans` (1 click from sidebar).
- Full scan history with filters by cloud account and status (pending / running / completed / failed).
- Per-row breakdown: duration, controls evaluated, pass/fail/total findings, scan type.
- **Auto-polls every 5 seconds** while any visible scan is running, so live progress updates without manual refresh.
- New backend endpoint `GET /api/v1/scans` with pagination, tenant isolation, and batched findings aggregation (no N+1 queries).
- Accounts page retains a per-account shortcut: `Scans` button deep-links to `/scans?cloud_account_id=<id>` pre-filtered by that account.

**🔧 CI/CD hardening**

- Backend Dockerfile now runs `apt-get update && apt-get upgrade` to pick up the latest Debian security patches at build time.
- New `.trivyignore` at repo root documents accepted-risk HIGH CVEs (ncurses CVE-2025-69720, systemd CVE-2026-29111) with rationale for why they are not exploitable in the container (no interactive CLI, no systemd as PID 1).
- `trivy-action` now reads `.trivyignore` so the image scan passes without blocking unrelated Debian base-layer findings.

### Next on the roadmap

- **Defender assessment enricher** — read `Microsoft.Security/assessments` for subscriptions where the collector detected Defender is ON, unblocking the remaining `CIS-AZ-19` (VM endpoint protection) and `CIS-AZ-20` (system updates) orphan controls plus ~10 new sub-assessments.
- **Entra ID / Microsoft Graph collector** — unlocks the MFA controls (CIS-AZ-01, 02), Conditional Access policies, PIM status. Blocked on granting `Directory.Read.All` + `Policy.Read.All` to the service principal.
- **Scan drill-down page `/scans/{id}`** — delta findings vs previous scan, pass/fail donut, deep-link into Findings filtered by scan.
- **Diagnostic settings enforcement coverage** — extend the single storage-only check into a per-resource-type sweep.

---

## Architecture

```
                          ┌─────────────────────┐
                          │   Next.js 14 (UI)   │ :3000
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │   FastAPI Backend    │ :8000
                          │   (async, JWT auth)  │
                          └──┬──────────────┬───┘
                             │              │
                    ┌────────▼──┐    ┌──────▼──────┐
                    │ PostgreSQL │    │ Celery + Redis│
                    │     16     │    │  (scan jobs)  │
                    └────────────┘    └──────┬───────┘
                                             │
                              ┌──────────────▼──────────────┐
                              │     Cloud Collectors         │
                              │  Azure Resource Graph        │
                              │  Defender for Cloud          │
                              │  AWS (IAM, EC2, S3, ...)     │
                              └──────────────────────────────┘
```

### Tech Stack

| Layer           | Technology                                                  |
| --------------- | ----------------------------------------------------------- |
| **Frontend**    | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts |
| **Backend**     | Python 3.10+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2  |
| **Database**    | PostgreSQL 16                                               |
| **Cache/Queue** | Redis 7, Celery                                             |
| **Auth**        | JWT (httpOnly cookies), bcrypt, TOTP/MFA, SSO/OIDC          |
| **Infra**       | Docker Compose, Alembic migrations                          |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ and pnpm (for frontend dev)
- Python 3.10+ and uv (for backend dev)

### 1. Clone and start

```bash
git clone https://github.com/cereZ23/nimbusguard.git
cd nimbusguard
docker compose up
```

This starts PostgreSQL, Redis, the backend API (`:8000`), Celery worker, and the frontend (`:3000`).

### 2. Run migrations

```bash
cd backend
alembic upgrade head
```

### 3. Seed security controls

```bash
cd backend
python -c "
import asyncio
from app.services.seed_controls import seed_controls
from app.database import async_session
asyncio.run(seed_controls(async_session()))
"
```

### 4. Open the UI

Navigate to [http://localhost:3000](http://localhost:3000), register an account, and connect your first cloud subscription.

---

## Development Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Start dev server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest -v --cov=app
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev      # http://localhost:3000
pnpm test     # run tests
pnpm lint     # lint check
```

### Database migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## Security Checks Coverage

NimbusGuard evaluates **162 security checks** across two cloud providers:

### Azure (142 controls)

| Category                                        | Checks | Examples                                                                                                                                                                                   |
| ----------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Subscription-level** (NEW data source)        | 10     | Defender for Cloud plans (Servers, Storage, SQL, App Service, Containers, Key Vault), security contacts, auto-provisioning, owner count                                                    |
| **Storage**                                     | 15     | HTTPS-only, encryption, public access, versioning, cross-tenant replication, standard DNS endpoint                                                                                         |
| **Web Apps (App Service)**                      | 16     | HTTPS, TLS 1.2+, FTP off, managed identity, CORS no wildcard, health check path, IP restrictions                                                                                           |
| **App Service Plans** (NEW)                     | 4      | Not on Free/Shared tier, zone redundancy, multiple workers for HA, per-site scaling on multi-site                                                                                          |
| **AKS (Managed Kubernetes)**                    | 11     | RBAC, network policy, private cluster, AAD integration, API authorized IPs, managed identity, Azure Policy add-on, Workload Identity, local accounts off, Azure RBAC, auto-upgrade channel |
| **Container Registry (ACR)**                    | 8      | Admin disabled, public access, anonymous pull, network default deny, quarantine, content trust, retention, CMK encryption                                                                  |
| **Key Vault**                                   | 8      | Purge protection, soft delete, RBAC, key/secret/cert expiration                                                                                                                            |
| **SQL & Databases**                             | 6      | TDE, public access, TLS, AAD admin, auditing, geo-redundant backup                                                                                                                         |
| **PostgreSQL flex**                             | 6      | SSL enforcement, log checkpoints, public access off, min TLS 1.2, geo-redundant backup, retention ≥ 7d                                                                                     |
| **MySQL flex**                                  | 5      | SSL, public access, min TLS 1.2, geo-redundant backup, retention ≥ 7d                                                                                                                      |
| **Cosmos DB**                                   | 6      | Public access, VNet filter, CMK, automatic failover, continuous backup, periodic retention                                                                                                 |
| **Recovery Services Vaults** (NEW)              | 5      | Geo-redundant storage, soft delete, cross-region restore, public access off, immutability                                                                                                  |
| **Log Analytics Workspaces**                    | 6      | Retention ≥ 90d, CMK encryption, daily quota, public access off (query + ingestion), RBAC-only                                                                                             |
| **Network Security Groups**                     | 6      | SSH/RDP restricted, flow logs, management ports (SMB/NetBIOS/WinRM), database ports, no wildcard any-port rule                                                                             |
| **Public IPs**                                  | 3      | DDoS protection, Standard SKU (not deprecated Basic), not orphaned                                                                                                                         |
| **Azure Firewall** (NEW)                        | 1      | Threat intelligence in Deny mode                                                                                                                                                           |
| **Networking (advanced)**                       | 7      | App Gateway WAF, Front Door HTTPS, VPN gateway SKU, VNet DDoS, Network Watcher                                                                                                             |
| **Compute**                                     | 4      | Managed disks, encryption, secure boot, boot diagnostics                                                                                                                                   |
| **Redis**                                       | 3      | Non-SSL ports, TLS version, public access                                                                                                                                                  |
| **Monitoring**                                  | 2      | Activity log alerts, diagnostic logs                                                                                                                                                       |
| **Other** (Batch, Service Bus, Event Hub, RBAC) | 10     | Event Hub encryption, Service Bus, Batch pools, custom roles, managed disks, NIC IP forwarding                                                                                             |

### AWS (20 controls)

| Category       | Checks | Examples                                                           |
| -------------- | ------ | ------------------------------------------------------------------ |
| **IAM**        | 4      | Root MFA, password policy, access key rotation, unused credentials |
| **S3**         | 4      | Public access block, encryption, versioning, logging               |
| **EC2**        | 3      | IMDSv2, public IPs, security group rules                           |
| **CloudTrail** | 1      | Multi-region trail enabled                                         |
| **RDS**        | 3      | Encryption, public access, multi-AZ                                |
| **VPC**        | 3      | Flow logs, default SG rules, NACLs                                 |
| **Lambda**     | 2      | Runtime version, public access                                     |

All checks are mapped to **CIS Benchmark v3.0** control IDs.

---

## API

Base URL: `/api/v1/`

Response envelope: `{ data, error, meta }`

### Core Endpoints

| Method | Endpoint               | Description                                       |
| ------ | ---------------------- | ------------------------------------------------- |
| `POST` | `/auth/register`       | Register tenant + admin user                      |
| `POST` | `/auth/login`          | Authenticate (returns JWT in httpOnly cookie)     |
| `POST` | `/auth/mfa/setup`      | Initiate MFA setup (TOTP)                         |
| `POST` | `/auth/mfa/login`      | Complete MFA challenge                            |
| `CRUD` | `/accounts`            | Cloud account management                          |
| `GET`  | `/assets`              | List assets (paginated, filterable)               |
| `GET`  | `/findings`            | List findings (paginated, filterable, sortable)   |
| `POST` | `/findings/bulk-waive` | Bulk waive findings                               |
| `GET`  | `/dashboard/summary`   | Aggregated security posture                       |
| `POST` | `/scans`               | Trigger scan (idempotent, 409 if already running) |
| `GET`  | `/scans`               | List scans (filter by account/status, paginated)  |
| `GET`  | `/scans/{id}`          | Get single scan with findings breakdown           |
| `GET`  | `/compliance`          | CIS compliance overview                           |
| `GET`  | `/export/pdf`          | Download PDF evidence pack                        |
| `CRUD` | `/roles`               | Custom RBAC roles                                 |
| `CRUD` | `/invitations`         | Team invitations                                  |
| `CRUD` | `/sso/config`          | SSO/OIDC configuration                            |
| `GET`  | `/audit-logs`          | Audit trail (admin only)                          |

Full API documentation available at `/docs` (Swagger UI) when running the backend.

---

## Project Structure

```
nimbusguard/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI route handlers (30 modules)
│   │   ├── config/           # Settings, control_mappings.yaml
│   │   ├── models/           # SQLAlchemy models (10 core tables)
│   │   ├── schemas/          # Pydantic v2 request/response schemas
│   │   ├── services/         # Business logic
│   │   │   ├── azure/        # Azure collectors + 28 check modules
│   │   │   │   ├── collector.py              # Resource Graph collector
│   │   │   │   ├── subscription_collector.py # Subscription-level state (Defender, contacts, RBAC)
│   │   │   │   └── checks/                   # 142 Azure security checks
│   │   │   ├── aws/          # AWS collector + check modules
│   │   │   │   └── checks/   # 20 AWS security checks
│   │   │   ├── auth.py       # Authentication service
│   │   │   ├── mfa.py        # TOTP/backup codes
│   │   │   ├── sso.py        # OIDC discovery + callbacks
│   │   │   └── evaluator.py  # Check registry + orchestration
│   │   ├── worker/           # Celery tasks (scan pipeline)
│   │   └── deps.py           # DI: auth, tenancy, DB session
│   ├── alembic/              # Database migrations
│   ├── tests/                # 1273 tests (pytest)
│   │   ├── api/              # Integration tests
│   │   └── services/         # Unit tests (checks, auth, etc.)
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js 14 pages (App Router)
│   │   ├── components/       # React components
│   │   └── lib/              # Utilities, API client, auth
│   └── package.json
├── docker-compose.yml
└── README.md
```

---

## Testing

```bash
# Backend — 1273 tests
cd backend && pytest -v --cov=app

# Frontend — 81 unit tests
cd frontend && pnpm test

# E2E (Playwright)
cd frontend && pnpm exec playwright test
```

Test categories:

- **API integration tests** — auth, accounts, assets, findings, SSO, MFA, roles, invitations, dashboard, scans (14 tests covering trigger + list + filters + tenant isolation), export, RBAC, audit, branding, API keys
- **Security check unit tests** — 162 checks × pass/fail/missing-property/null scenarios (4+ tests per check)
- **E2E tests** — 50 Playwright tests across login, dashboard, findings, assets, export, compliance, settings

---

## Azure Permissions

NimbusGuard requires **read-only** access. Assign these built-in roles at the management group or subscription level:

- `Reader` — resource inventory via Resource Graph
- `Security Reader` — Defender for Cloud secure score and recommendations

No write access is ever needed.

---

## Environment Variables

| Variable                    | Description                      | Default                                              |
| --------------------------- | -------------------------------- | ---------------------------------------------------- |
| `SECRET_KEY`                | JWT signing key                  | Required in production                               |
| `DATABASE_URL`              | PostgreSQL connection string     | `postgresql+asyncpg://cspm:cspm@localhost:5432/cspm` |
| `REDIS_URL`                 | Redis connection string          | `redis://localhost:6379/0`                           |
| `CELERY_BROKER_URL`         | Celery broker                    | `redis://localhost:6379/1`                           |
| `CREDENTIAL_ENCRYPTION_KEY` | Fernet key for cloud credentials | Auto-generated in debug                              |
| `DEBUG`                     | Enable debug mode                | `false`                                              |

---

## Contributing: Adding New Security Checks

NimbusGuard's check engine is designed for easy extensibility. Adding a new check takes ~10 minutes: write the check function, register it with a decorator, add the control definition, and write tests.

### Architecture overview

```
@check(resource_type, control_code)        ← decorator registers the function
def check_something(asset: Asset) -> EvalResult:
    props = asset.raw_properties or {}     ← extract properties from the cloud asset
    value = props.get("someProperty", False)
    return EvalResult(                     ← return pass/fail + evidence
        status="pass" if value else "fail",
        evidence={"someProperty": value},
        description="Human-readable explanation",
    )
```

The evaluator engine automatically discovers all registered checks, matches them to assets by `resource_type`, and creates findings in the database.

### Step 1: Write the check function

Create a new file (or add to an existing one) under the appropriate provider directory:

```
backend/app/services/azure/checks/   ← Azure checks
backend/app/services/aws/checks/     ← AWS checks
```

**Azure example** — `backend/app/services/azure/checks/my_service.py`:

```python
"""My Service checks (CIS-AZ-XX)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.myservice/resources", "CIS-AZ-85")
def check_encryption_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-85: My Service should have encryption enabled."""
    props = asset.raw_properties or {}
    encrypted = props.get("encryption", {}).get("enabled", False)
    return EvalResult(
        status="pass" if encrypted else "fail",
        evidence={"encryption.enabled": encrypted},
        description="Encryption is enabled"
        if encrypted
        else "Encryption is NOT enabled — data at rest is unprotected",
    )
```

**AWS example** — `backend/app/services/aws/checks/my_service.py`:

```python
"""My Service checks (CIS-AWS-XX)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.myservice.resource", "CIS-AWS-21")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AWS-21: My Service should not allow public access."""
    props = asset.raw_properties or {}
    is_public = props.get("IsPublic", True)
    return EvalResult(
        status="pass" if not is_public else "fail",
        evidence={"IsPublic": is_public},
        description="Public access is disabled"
        if not is_public
        else "Public access is enabled — restrict access immediately",
    )
```

**Rules:**

- The `resource_type` must match exactly what the collector stores in the asset (lowercase for Azure, `aws.service.resource` for AWS)
- Always handle `raw_properties` being `None` or empty `{}`
- Always default to **fail** when properties are missing (secure by default)
- Include meaningful evidence and description

### Step 2: Register the module

Add your import to the provider's `__init__.py`:

**Azure** — `backend/app/services/azure/checks/__init__.py`:

```python
from app.services.azure.checks import (  # noqa: F401
    # ... existing imports ...
    my_service,          # ← add this line
)
```

**AWS** — `backend/app/services/aws/checks/__init__.py`:

```python
from app.services.aws.checks import (  # noqa: F401
    # ... existing imports ...
    my_service,          # ← add this line
)
```

### Step 3: Add the control definition

Add a new entry to `backend/app/config/control_mappings.yaml`:

```yaml
- code: CIS-AZ-85
  name: My Service encryption enabled
  description: My Service resources should have encryption at rest enabled
  severity: high
  framework: cis-lite
  remediation_hint: Enable encryption in the resource settings via Azure Portal or CLI
  provider_check_ref:
    azure: null
    aws: null
  framework_mappings:
    soc2:
      - CC6.1
    nist:
      - SC-28
    iso27001:
      - A.8.24
```

Then seed the controls into the database:

```bash
cd backend
python -c "
import asyncio
from app.services.seed_controls import seed_controls
from app.database import async_session
asyncio.run(seed_controls(async_session()))
"
```

### Step 4: Write tests

Create `backend/tests/services/test_checks_my_service.py`:

```python
"""Unit tests for My Service checks."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.my_service import check_encryption_enabled


def _make_asset(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/microsoft.myservice/resources/test",
        resource_type="microsoft.myservice/resources",
        name="test-resource",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckEncryptionEnabled:
    def test_pass_when_encryption_enabled(self):
        asset = _make_asset({"encryption": {"enabled": True}})
        result = check_encryption_enabled(asset)
        assert result.status == "pass"
        assert result.evidence["encryption.enabled"] is True

    def test_fail_when_encryption_disabled(self):
        asset = _make_asset({"encryption": {"enabled": False}})
        result = check_encryption_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_encryption_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_encryption_enabled(asset)
        assert result.status == "fail"
```

**Every check needs at least 4 tests:**

| Test case                            | What it validates                                     |
| ------------------------------------ | ----------------------------------------------------- |
| `test_pass_when_*`                   | Correct property value → `"pass"`                     |
| `test_fail_when_*`                   | Incorrect property value → `"fail"`                   |
| `test_fail_when_property_missing`    | Empty `raw_properties={}` → `"fail"` (secure default) |
| `test_fail_when_raw_properties_none` | `raw_properties=None` → `"fail"` (null safety)        |

### Step 5: Update the registry test

Update the expected count in `backend/tests/services/test_evaluator.py`:

```python
def test_registry_total_check_count(self):
    all_checks = registry.all_checks
    assert len(all_checks) == 101   # ← bump from 100 to 101
```

### Step 6: Run tests

```bash
cd backend
pytest tests/services/test_checks_my_service.py -v    # new check tests
pytest tests/services/test_evaluator.py -v             # registry test
pytest -v                                              # full suite
```

### Resource type naming conventions

| Provider  | Format                                       | Examples                                                                                              |
| --------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Azure** | `microsoft.<service>/<resource>` (lowercase) | `microsoft.storage/storageaccounts`, `microsoft.compute/virtualmachines`, `microsoft.keyvault/vaults` |
| **AWS**   | `aws.<service>.<resource>` (lowercase)       | `aws.s3.bucket`, `aws.ec2.instance`, `aws.iam.user`, `aws.rds.instance`                               |

### Collector integration (if new resource type)

If your check targets a resource type that the collector doesn't yet collect, you'll need to add a query to the appropriate collector:

**Azure** — `backend/app/services/azure/collector.py`:
The generic inventory query already collects all Azure resource types via Resource Graph. If you need specific sub-resources or additional properties, add a new `_collect_*()` method.

**AWS** — `backend/app/services/aws/collector.py`:
Add a new boto3 API call to fetch the resource type and create `Asset` records with the appropriate `resource_type` and `raw_properties`.

### Summary checklist

- [ ] Check function in `app/services/{azure,aws}/checks/`
- [ ] Import added to `checks/__init__.py`
- [ ] Control entry in `control_mappings.yaml`
- [ ] Seed controls into DB
- [ ] 4+ tests in `tests/services/test_checks_*.py`
- [ ] Registry count updated in `test_evaluator.py`
- [ ] All tests pass (`pytest -v`)

---

## Roadmap

### Done

- [x] Azure Resource Graph collector
- [x] **162 Azure CIS-Lite controls** (84 foundational + 79 added April 2026)
- [x] **Priority/Triage layer (P0..P3)** with transparent yaml-driven formula, dashboard overview card, Secure Score projection, top-10 grouped remediation actions, findings page priority column + filter
- [x] **Subscription-level collector** — Defender plans, security contacts, auto-provisioning, owner count (CIS-AZ-104..113)
- [x] **Backup & DR posture checks** (CIS-AZ-114..121) — Recovery Services Vaults, SQL, Cosmos DB
- [x] **Network exposure hardening** (CIS-AZ-122..127) — management/DB ports, wildcard rules, Public IP, Azure Firewall
- [x] **AKS deep hardening** (CIS-AZ-128..134) — private cluster, Workload Identity, Azure RBAC, auto-upgrade
- [x] **ACR supply-chain controls** (CIS-AZ-135..140) — anonymous pull, quarantine, content trust, CMK
- [x] **PG/MySQL flex hardening** (CIS-AZ-141..146) — TLS, public access, geo-redundant backup, retention
- [x] **VM deep hardening** (CIS-AZ-147..153) — Trusted Launch, vTPM, managed identity, auto-patching, availability
- [x] **Diagnostic settings sweep** (CIS-AZ-154..163) — 10 critical resource types (SQL, Key Vault, Web App, VM, Cosmos, AKS, App Gateway, Front Door, Service Bus, NSG) with a new Resource Graph collector query
- [x] 20 AWS CIS controls
- [x] Multi-tenant architecture
- [x] SSO/OIDC + MFA
- [x] Custom RBAC
- [x] PDF evidence export
- [x] Scheduled scans
- [x] Jira & Slack integrations
- [x] **Dedicated `/scans` page** with history, filters, and live auto-refresh
- [x] **Hardened CI/CD** — Dockerfile base image auto-upgrade + Trivy allow-list for unpatchable Debian CVEs

### Planned

- [ ] **Smart alerting** — send Slack / email / webhook notifications on scan completion filtered by priority (e.g. "only notify me on new P0 findings"). Builds on the triage layer
- [ ] **Remediation playbooks** — bulk ticket creation in Jira / one-click auto-remediation for selected remediation groups
- [ ] **Entra ID / Microsoft Graph collector** — tenant-level MFA controls (CIS-AZ-01, 02), Conditional Access policies, PIM status. Blocked on granting `Directory.Read.All` + `Policy.Read.All` to the service principal
- [ ] Scan drill-down page `/scans/{id}` with delta findings vs previous scan
- [ ] Onboarding UX polish (copy-paste CLI for service principal, inline validation, better confirm step)
- [ ] RBAC least-privilege deep checks (stale role assignments, over-privileged service principals, custom role wildcard permissions)
- [ ] GCP support (Cloud Asset Inventory + CIS GCP benchmark)
- [ ] Kubernetes support (CIS Kubernetes Benchmark + Pod Security Standards)
- [ ] Auto-remediation playbooks
- [ ] SCIM user provisioning
- [ ] Terraform/IaC scanning
- [ ] Custom policy engine (OPA/Rego)
- [ ] Observability stack (Loki + Grafana) for operational logs

### Known issues / deferred

- `.trivyignore` contains 2 accepted-risk HIGH CVEs (ncurses CVE-2025-69720, systemd CVE-2026-29111) waiting for Debian patches. Periodically re-check and remove entries as they are fixed upstream.
- CI backend test job takes ~10 minutes to run 1273 tests. The main bottlenecks are tenant-isolation test setup (~1s per test × 19 tests) and coverage instrumentation (~25% overhead). `pytest-xdist` parallelization was attempted but blocked on per-worker DB isolation — tracked as a future refactor.

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built by <a href="https://github.com/cereZ23">cerez23</a>
</p>
