# Contributing to NimbusGuard

Thanks for your interest in NimbusGuard. This guide covers the two most
common contributions:

1. [Adding new security checks](#adding-new-security-checks) — the fastest
   way to improve coverage of an existing cloud provider.
2. [General development workflow](#general-development-workflow) — branch
   conventions, testing, and CI expectations.

> For architecture overview and data model, see
> [`CLAUDE.md`](../CLAUDE.md) and [`README.md`](../README.md).
> For the full controls catalogue, see [`docs/CONTROLS.md`](CONTROLS.md).

---

## Adding new security checks

NimbusGuard's check engine is designed for easy extensibility. Adding a
new check takes ~10 minutes: write the function, register it with a
decorator, add the yaml entry, write tests, bump the registry count.

### Architecture at a glance

```
@check(resource_type, control_code)        ← decorator registers the function
def check_something(asset: Asset) -> EvalResult:
    props = asset.raw_properties or {}     ← extract properties from the asset
    value = props.get("someProperty", False)
    return EvalResult(                     ← return pass/fail + evidence
        status="pass" if value else "fail",
        evidence={"someProperty": value},
        description="Human-readable explanation",
    )
```

The evaluator engine automatically discovers every registered check,
matches it to assets by `resource_type`, and creates findings. No routing
or wiring by hand.

### Step 1 — Write the check function

Create a new file (or extend an existing one) under the provider
directory:

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


@check("microsoft.myservice/resources", "CIS-AZ-180")
def check_encryption_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-180: My Service should have encryption enabled."""
    props = asset.raw_properties or {}
    encrypted = props.get("encryption", {}).get("enabled", False)
    return EvalResult(
        status="pass" if encrypted else "fail",
        evidence={"encryption.enabled": encrypted},
        description=(
            "Encryption is enabled"
            if encrypted
            else "Encryption is NOT enabled — data at rest is unprotected"
        ),
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
        description=(
            "Public access is disabled"
            if not is_public
            else "Public access is enabled — restrict access immediately"
        ),
    )
```

**Rules:**

- `resource_type` must match **exactly** what the collector stores on the
  asset (lowercase for Azure, `aws.service.resource` for AWS).
- Always handle `raw_properties` being `None` or empty `{}`.
- Always default to **`fail`** when properties are missing
  (secure-by-default).
- Include meaningful evidence and a human-readable description — both are
  surfaced in the UI and PDF exports.

### Step 2 — Register the module

Add the import to the provider's `__init__.py`:

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

### Step 3 — Add the yaml control definition

Add a new entry to
[`backend/app/config/control_mappings.yaml`](../backend/app/config/control_mappings.yaml):

```yaml
- code: CIS-AZ-180
  name: My Service encryption enabled
  description: My Service resources should have encryption at rest enabled
  severity: high
  framework: cis-lite
  remediation_hint: >
    Enable encryption in the resource settings via Azure Portal or CLI
  # Optional priority metadata (see docs/CONTROLS.md#priority-metadata)
  effort: quick
  exposure: internal
  remediation_group: enable_encryption_at_rest
  remediation_action: >
    Enable encryption at rest on all My Service resources
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

Then seed the controls into the local DB:

```bash
cd backend
python -c "
import asyncio
from app.services.seed_controls import seed_controls
from app.database import async_session
asyncio.run(seed_controls(async_session()))
"
```

### Step 4 — Write tests

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
        provider_id=(
            f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/"
            "providers/microsoft.myservice/resources/test"
        ),
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

### Step 5 — Bump the registry count

Update the expected count in `backend/tests/services/test_evaluator.py`:

```python
def test_registry_total_check_count(self):
    all_checks = registry.all_checks
    assert len(all_checks) == 180   # ← bump by +1
```

### Step 6 — Run tests

```bash
cd backend
pytest tests/services/test_checks_my_service.py -v   # new check tests
pytest tests/services/test_evaluator.py -v           # registry test
pytest -v                                            # full suite
```

### Collector integration (only if new resource type)

If your check targets a resource type that the collector doesn't yet
collect, add a query to the appropriate collector:

- **Azure** — `backend/app/services/azure/collector.py`
  The generic inventory query already pulls every Azure resource type via
  Resource Graph. If you need sub-resources or additional properties, add
  a new `_collect_*()` method. For cross-resource data (like diagnostic
  settings), see `_collect_diagnostic_settings()` as a reference.
- **AWS** — `backend/app/services/aws/collector.py`
  Add a new boto3 API call, create `Asset` records with the proper
  `resource_type` and `raw_properties`.

### Resource type naming conventions

| Provider  | Format                                       | Examples                                                                                              |
| --------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Azure** | `microsoft.<service>/<resource>` (lowercase) | `microsoft.storage/storageaccounts`, `microsoft.compute/virtualmachines`, `microsoft.keyvault/vaults` |
| **AWS**   | `aws.<service>.<resource>` (lowercase)       | `aws.s3.bucket`, `aws.ec2.instance`, `aws.iam.user`, `aws.rds.instance`                               |

### Summary checklist

- [ ] Check function in `app/services/{azure,aws}/checks/`
- [ ] Import added to `checks/__init__.py`
- [ ] Control entry in `control_mappings.yaml`
  - [ ] Optional: `effort`, `exposure`, `remediation_group` for priority layer
- [ ] Seed controls into DB
- [ ] 4+ tests in `tests/services/test_checks_*.py`
- [ ] Registry count updated in `test_evaluator.py`
- [ ] All tests pass (`pytest -v`)

---

## General development workflow

### Branch conventions

- `feature/<name>` — new functionality
- `fix/<name>` — bug fix
- `chore/<name>` — maintenance, refactor, CI
- `hotfix/<name>` — urgent production fix

### Commit convention

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scans): dedicated /scans page with history and live updates
fix(ci): unblock Trivy gate after Debian base image CVE refresh
chore(azure): ruff lint + format on new Azure CIS-Lite controls
```

Scope is optional but encouraged. Language is English.

### Tests

```bash
# Backend — 1273 tests with coverage
cd backend
pytest -v --cov=app

# Run a single file
pytest tests/api/test_findings.py -v

# Frontend — 81 unit tests
cd frontend
pnpm test

# E2E — 50 Playwright tests
cd frontend
pnpm exec playwright test
```

CI runs the full backend suite, ruff lint + format, mypy, Trivy image
scan, and the frontend build + tests on every PR. Don't skip hooks
(`--no-verify`) — if a hook fails, fix the issue and re-commit.

### Database migrations

```bash
cd backend
alembic revision --autogenerate -m "add priority layer fields"
# Review the generated file carefully, then:
alembic upgrade head
```

Never modify a migration that has already been applied in production.
Create a new one instead.

### Multi-tenancy

**Every query must filter by `effective_tenant_id`** — never touch
`tenant_id` directly. See `app/deps.py` for the dependency. Tests cover
tenant isolation explicitly; run `pytest tests/api/test_multitenancy.py`
after any data-access changes.

### Code style

- Python: `ruff` + `mypy` (auto-run on save via plugin hook)
- TypeScript: `eslint` + `prettier` (auto-run on save)
- No `print()` in Python code — use `logging.getLogger(__name__)`.
- No `any` in TypeScript — define proper types.
- Never hardcode secrets — use environment variables.

### Reporting bugs / requesting features

Open an issue on GitHub with:

- **For bugs** — reproduction steps, expected vs actual behavior, logs
  from the backend (`docker compose logs backend`), and the scan ID if
  relevant.
- **For features** — the use case, the expected UI/API shape, and any
  reference implementation you've seen elsewhere.
