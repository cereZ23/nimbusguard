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
  <img src="https://img.shields.io/badge/tests-803_passing-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License" />
</p>

---

## What is NimbusGuard?

NimbusGuard is a **multi-tenant CSPM** (Cloud Security Posture Management) platform that continuously scans your cloud infrastructure, evaluates it against **100+ security checks** mapped to CIS Benchmarks, and gives you a clear picture of your security posture — all from a single dashboard.

### Key Features

- **100 built-in security checks** across Azure (84 controls) and AWS (20 controls), mapped to CIS v3.0
- **Multi-cloud support** — Azure today, AWS in progress, GCP on the roadmap
- **Real-time Secure Score** — aggregated per-account and cross-cloud
- **Asset inventory** — full visibility into every cloud resource, searchable and filterable
- **Findings management** — prioritized by severity, with remediation guidance and evidence
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

NimbusGuard evaluates **100 security checks** across two cloud providers:

### Azure (84 controls)

| Category                  | Checks | Examples                                                        |
| ------------------------- | ------ | --------------------------------------------------------------- |
| **Storage**               | 10     | HTTPS-only, encryption, public access, soft delete, versioning  |
| **Networking**            | 3      | NSG SSH/RDP rules, flow logs                                    |
| **Key Vault**             | 8      | Purge protection, soft delete, RBAC, key/secret/cert expiration |
| **Web Apps**              | 10     | HTTPS, TLS 1.2, FTP disabled, managed identity, remote debug    |
| **SQL & Databases**       | 5      | TDE, public access, TLS, AAD admin, auditing                    |
| **Compute**               | 4      | Managed disks, encryption, secure boot, boot diagnostics        |
| **Cosmos DB**             | 4      | Public access, VNet filter, CMK, automatic failover             |
| **PostgreSQL**            | 2      | SSL enforcement, log checkpoints                                |
| **MySQL**                 | 3      | SSL, audit logging, public access                               |
| **Container (ACR/AKS)**   | 6      | Admin disabled, RBAC, network policy, quarantine                |
| **Redis**                 | 3      | Non-SSL ports, TLS version, public access                       |
| **Networking (advanced)** | 8      | App Gateway WAF, Front Door HTTPS, VPN, public IPs              |
| **Monitoring**            | 3      | Activity log alerts, Log Analytics retention, Network Watcher   |
| **Other**                 | 15     | Event Hub encryption, Service Bus, Batch pools, managed disks   |

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

| Method | Endpoint               | Description                                     |
| ------ | ---------------------- | ----------------------------------------------- |
| `POST` | `/auth/register`       | Register tenant + admin user                    |
| `POST` | `/auth/login`          | Authenticate (returns JWT in httpOnly cookie)   |
| `POST` | `/auth/mfa/setup`      | Initiate MFA setup (TOTP)                       |
| `POST` | `/auth/mfa/login`      | Complete MFA challenge                          |
| `CRUD` | `/accounts`            | Cloud account management                        |
| `GET`  | `/assets`              | List assets (paginated, filterable)             |
| `GET`  | `/findings`            | List findings (paginated, filterable, sortable) |
| `POST` | `/findings/bulk-waive` | Bulk waive findings                             |
| `GET`  | `/dashboard/summary`   | Aggregated security posture                     |
| `POST` | `/scans`               | Trigger scan (idempotent)                       |
| `GET`  | `/compliance`          | CIS compliance overview                         |
| `GET`  | `/export/pdf`          | Download PDF evidence pack                      |
| `CRUD` | `/roles`               | Custom RBAC roles                               |
| `CRUD` | `/invitations`         | Team invitations                                |
| `CRUD` | `/sso/config`          | SSO/OIDC configuration                          |
| `GET`  | `/audit-logs`          | Audit trail (admin only)                        |

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
│   │   │   ├── azure/        # Azure collector + 23 check modules
│   │   │   │   └── checks/   # 84 Azure security checks
│   │   │   ├── aws/          # AWS collector + check modules
│   │   │   │   └── checks/   # 20 AWS security checks
│   │   │   ├── auth.py       # Authentication service
│   │   │   ├── mfa.py        # TOTP/backup codes
│   │   │   ├── sso.py        # OIDC discovery + callbacks
│   │   │   └── evaluator.py  # Check registry + orchestration
│   │   ├── worker/           # Celery tasks (scan pipeline)
│   │   └── deps.py           # DI: auth, tenancy, DB session
│   ├── alembic/              # Database migrations
│   ├── tests/                # 803 tests (pytest)
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
# Backend — 803 tests
cd backend && pytest -v --cov=app

# Frontend
cd frontend && pnpm test

# E2E (Playwright)
cd frontend && pnpm exec playwright test
```

Test categories:

- **API integration tests** — auth, accounts, assets, findings, SSO, MFA, roles, invitations, dashboard, scans, export, RBAC, audit, branding, API keys
- **Security check unit tests** — 100 checks × pass/fail/missing-property/null scenarios
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

- [x] Azure Resource Graph collector
- [x] 84 Azure CIS controls
- [x] 20 AWS CIS controls
- [x] Multi-tenant architecture
- [x] SSO/OIDC + MFA
- [x] Custom RBAC
- [x] PDF evidence export
- [x] Scheduled scans
- [x] Jira & Slack integrations
- [ ] GCP support
- [ ] Auto-remediation playbooks
- [ ] SCIM user provisioning
- [ ] Terraform/IaC scanning
- [ ] Custom policy engine (OPA/Rego)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built by <a href="https://github.com/cereZ23">cerez23</a>
</p>
