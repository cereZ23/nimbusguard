<p align="center">
  <img src="https://img.shields.io/badge/NimbusGuard-Cloud%20Security-0ea5e9?style=for-the-badge&logo=icloud&logoColor=white" alt="NimbusGuard" />
</p>

<h1 align="center">NimbusGuard</h1>

<p align="center">
  <strong>Cloud Security Posture Management — with a triage layer your team can actually act on.</strong><br/>
  Continuous security assessment for Azure and AWS, built for MSSPs and in-house security teams.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776ab?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js_14-000?logo=nextdotjs&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/PostgreSQL_16-4169e1?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/tests-1273_passing-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/checks-179-0ea5e9" alt="Security Checks" />
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License" />
  <br/>
  <a href="https://github.com/cereZ23/nimbusguard/actions"><img src="https://github.com/cereZ23/nimbusguard/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/security-CIS%20Benchmarks%20v3.0-00b4d8" alt="CIS Benchmarks" />
</p>

---

## The problem NimbusGuard solves

Every CSPM gives you a long list of findings. Most tenants have **60 to
200 failing controls** on day one. A flat list is noise — the user opens
the page, sees red everywhere, closes it, and nothing gets fixed.

NimbusGuard turns that flat list into a **ranked action plan**:

- Every failing finding is bucketed into **P0 / P1 / P2 / P3** by a
  transparent 3×3 matrix of _severity × effort_, bumped up one tier when
  the finding is internet-exposed.
- Controls that share a fix are **grouped** so _"Enable Defender for
  Cloud Standard plan"_ shows up once and resolves six findings at once.
- The dashboard projects **Secure Score before / after fixing P0 / after
  fixing P0 + P1**, so the team sees exactly how much posture one week
  of fixes will buy.

No black-box ML. No proprietary scoring. The formula lives in
[`control_mappings.yaml`](backend/app/config/control_mappings.yaml) and
is 100% customisable per tenant.

> **Live example from a production Azure tenant (6 assets, 86 evaluations):**
>
> | Bucket     | Count  | Meaning         |
> | ---------- | ------ | --------------- |
> | 🔴 **P0**  | **25** | Fix now         |
> | 🟠 **P1**  | **29** | Fix this week   |
> | 🟡 **P2**  | **8**  | Fix this sprint |
> | 🟢 **P3**  | **3**  | Best practice   |
> | Total fail | **65** |                 |
>
> Current Secure Score **24.4%** → **53.5%** after P0 → **87.2%** after P0 + P1.

---

## Why NimbusGuard

### 1. Triage is the product, not a nice-to-have

Wiz, Prisma Cloud, Defender CSPM, Orca all use proprietary black-box ML
scoring that buyers can't inspect or customise. Open-source CSPMs
(Prowler, Steampipe, ScoutSuite) have **zero triage** — just a flat list
of findings. NimbusGuard's triage formula is transparent, yaml-driven,
and editable. That is the moat.

### 2. 179 built-in security checks, mapped to CIS v3.0

- **159 Azure evaluators** across 34 resource types — subscription-level
  Defender state, AKS, ACR, Key Vault, SQL, PostgreSQL / MySQL flex,
  Cosmos DB, Storage, Web Apps, App Service Plans, Networking, NSGs,
  Recovery Services Vaults, diagnostic settings sweep, and more.
- **20 AWS evaluators** across IAM, S3, EC2, RDS, VPC, CloudTrail,
  GuardDuty, Lambda.
- Full catalogue: [docs/CONTROLS.md](docs/CONTROLS.md).

### 3. Built for teams that actually fix things

- **Dedicated `/scans` page** with live 5-second auto-refresh while
  scans run.
- **Grouped remediation actions** — one click opens all findings that
  share a fix.
- **Bulk waive / comment / assign** on findings at scale.
- **PDF evidence packs** for audits and customer reports.
- **Jira & Slack integration** for pushing findings into existing
  workflows.
- **Multi-tenant from day one** — one instance, many customers, full
  isolation. Designed for MSSPs.
- **SSO/OIDC + MFA + custom RBAC** — Azure AD, Okta, Google Workspace,
  custom OIDC providers.

---

## Architecture

```
                          ┌─────────────────────┐
                          │   Next.js 14 (UI)   │ :3000
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │   FastAPI Backend   │ :8000
                          │  (async, JWT auth)  │
                          └──┬──────────────┬───┘
                             │              │
                    ┌────────▼──┐    ┌──────▼────────┐
                    │ PostgreSQL│    │ Celery + Redis│
                    │    16     │    │  (scan jobs)  │
                    └───────────┘    └──────┬────────┘
                                            │
                              ┌─────────────▼─────────────┐
                              │     Cloud Collectors      │
                              │  Azure Resource Graph     │
                              │  Defender for Cloud       │
                              │  AWS (IAM, EC2, S3, ...)  │
                              └───────────────────────────┘
```

| Layer           | Technology                                                  |
| --------------- | ----------------------------------------------------------- |
| **Frontend**    | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts |
| **Backend**     | Python 3.10+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2  |
| **Database**    | PostgreSQL 16                                               |
| **Cache/Queue** | Redis 7, Celery                                             |
| **Auth**        | JWT (httpOnly cookies), bcrypt, TOTP/MFA, SSO/OIDC          |
| **Infra**       | Docker Compose, Alembic migrations, Caddy (TLS)             |

---

## Quick start

### Prerequisites

Docker & Docker Compose, Node 18+ with pnpm (frontend dev), Python 3.10+
with uv (backend dev).

### 1. Clone and start

```bash
git clone https://github.com/cereZ23/nimbusguard.git
cd nimbusguard
docker compose up
```

This starts PostgreSQL, Redis, the FastAPI backend (`:8000`), a Celery
worker, and the Next.js frontend (`:3000`).

### 2. Run migrations + seed controls

```bash
cd backend
alembic upgrade head
python -c "
import asyncio
from app.services.seed_controls import seed_controls
from app.database import async_session
asyncio.run(seed_controls(async_session()))
"
```

### 3. Open the UI

Navigate to [http://localhost:3000](http://localhost:3000), register an
account, and connect your first cloud subscription.

### Azure permissions (read-only)

Assign these **built-in read-only roles** at the management group or
subscription level — no write access is ever needed:

- `Reader` — resource inventory via Resource Graph
- `Security Reader` — Defender for Cloud secure score and recommendations

---

## Development

```bash
# Backend
cd backend
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
pytest -v --cov=app                           # 1273 tests

# Frontend
cd frontend
pnpm install
pnpm dev                                      # http://localhost:3000
pnpm test                                     # 81 unit tests
pnpm exec playwright test                     # 50 E2E tests

# New migration
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Environment variables

| Variable                    | Description                      | Default                                              |
| --------------------------- | -------------------------------- | ---------------------------------------------------- |
| `SECRET_KEY`                | JWT signing key                  | **Required in production**                           |
| `DATABASE_URL`              | PostgreSQL connection string     | `postgresql+asyncpg://cspm:cspm@localhost:5432/cspm` |
| `REDIS_URL`                 | Redis connection string          | `redis://localhost:6379/0`                           |
| `CELERY_BROKER_URL`         | Celery broker                    | `redis://localhost:6379/1`                           |
| `CREDENTIAL_ENCRYPTION_KEY` | Fernet key for cloud credentials | Auto-generated in debug                              |
| `DEBUG`                     | Enable debug mode                | `false`                                              |

---

## API

Base URL: `/api/v1/`. Response envelope: `{ data, error, meta }`.
Interactive docs at `/docs` (Swagger UI) when the backend is running.

| Method | Endpoint                      | Description                                        |
| ------ | ----------------------------- | -------------------------------------------------- |
| `POST` | `/auth/register`              | Register tenant + admin user                       |
| `POST` | `/auth/login`                 | Authenticate (JWT in httpOnly cookie)              |
| `POST` | `/auth/mfa/login`             | Complete MFA challenge                             |
| `CRUD` | `/accounts`                   | Cloud account management                           |
| `GET`  | `/assets`                     | List assets (paginated, filterable)                |
| `GET`  | `/findings`                   | List findings (sort by priority, filter by bucket) |
| `GET`  | `/dashboard/summary`          | Aggregated security posture                        |
| `GET`  | `/dashboard/priority-summary` | Priority counts + Secure Score projection          |
| `POST` | `/scans`                      | Trigger scan (idempotent, 409 if already running)  |
| `GET`  | `/scans`                      | Scan history (filter by account + status)          |
| `GET`  | `/compliance`                 | Framework rollup (CIS, SOC2, NIST, ISO27001)       |
| `GET`  | `/export/pdf`                 | Download PDF evidence pack                         |

---

## Project layout

```
nimbusguard/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI route handlers (30 modules)
│   │   ├── config/           # Settings + control_mappings.yaml
│   │   ├── models/           # SQLAlchemy models (10 core tables)
│   │   ├── services/
│   │   │   ├── azure/checks/ # 159 Azure evaluators
│   │   │   ├── aws/checks/   # 20 AWS evaluators
│   │   │   ├── priority.py   # Priority / Triage calculator
│   │   │   ├── evaluator.py  # Check registry + orchestration
│   │   │   └── seed_controls.py
│   │   ├── worker/           # Celery scan pipeline
│   │   └── deps.py           # DI: auth, tenancy, DB session
│   ├── alembic/              # Migrations
│   └── tests/                # 1273 tests
├── frontend/
│   └── src/
│       ├── app/              # Next.js 14 pages (App Router)
│       └── components/       # React + Tailwind
├── docs/
│   ├── CONTROLS.md           # Full controls catalogue
│   ├── CONTRIBUTING.md       # Dev guide + adding new checks
│   └── ROADMAP.md            # Roadmap + rejected features
├── CHANGELOG.md              # Sprint log
├── docker-compose.yml
└── README.md
```

---

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** — every shipped sprint with commit SHA
- **[docs/CONTROLS.md](docs/CONTROLS.md)** — full catalogue of the 179 security checks
- **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** — dev workflow + how to add new checks in ~10 minutes
- **[docs/ROADMAP.md](docs/ROADMAP.md)** — what's next + what was explicitly rejected
- **[CLAUDE.md](CLAUDE.md)** — architecture notes and project conventions

---

## License

Apache License 2.0. See [LICENSE](LICENSE).

---

<p align="center">
  Built by <a href="https://github.com/cereZ23">cerez23</a>
</p>
