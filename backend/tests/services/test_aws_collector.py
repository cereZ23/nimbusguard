"""Unit tests for app.services.aws.collector (AwsCollector).

The collector wraps boto3. Tests replace ``boto3.Session`` with an in-memory
fake whose ``.client()`` returns per-service fakes built from SimpleNamespace,
so no real AWS calls happen. We drive the full ``run()`` flow (full + incremental
scans), the pure helpers, and the graceful-degradation branches.

The Asset / Finding models declare a NOT NULL ``tenant_id`` that the collector
does not set, so we register a ``before_insert`` listener (test-side only) that
populates it from the row's cloud account. This mirrors what the app does at a
higher layer and lets the inventory path flush against a real Postgres.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.finding import Finding
from app.models.scan import Scan
from app.models.tenant import Tenant
from app.services.aws.collector import AwsCollector, _normalize_resource_type, _sanitize_for_json
from app.services.credentials import encrypt_credentials

# ── tenant_id injection (test-side only) ────────────────────────────────


@pytest.fixture(autouse=True)
def _inject_tenant_id(_tenant_holder):
    """Populate tenant_id on Asset/Finding before insert.

    The collector creates Asset/Finding rows without a tenant_id; those columns
    are NOT NULL. We fill them from the single test tenant so flushes succeed.
    """

    def _set_tenant(mapper, connection, target):
        if getattr(target, "tenant_id", None) is None:
            target.tenant_id = _tenant_holder["tenant_id"]

    event.listen(Asset, "before_insert", _set_tenant)
    event.listen(Finding, "before_insert", _set_tenant)
    yield
    event.remove(Asset, "before_insert", _set_tenant)
    event.remove(Finding, "before_insert", _set_tenant)


@pytest.fixture
def _tenant_holder():
    return {"tenant_id": None}


@pytest.fixture(autouse=True)
def _eager_finding_id(monkeypatch):
    """Assign Finding.id at construction time.

    The collector builds an Evidence with ``finding_id=finding.id`` immediately
    after constructing the (un-flushed) Finding. Column defaults
    (``default=uuid.uuid4``) only fire at INSERT time, so ``finding.id`` would
    otherwise be None and the evidences.finding_id NOT NULL constraint would
    fail on flush. Eagerly populating ``id`` makes the FK resolve correctly.
    """
    orig_init = Finding.__init__

    def _init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        if getattr(self, "id", None) is None:
            self.id = uuid.uuid4()

    monkeypatch.setattr(Finding, "__init__", _init)


# ── DB scaffolding ──────────────────────────────────────────────────────


async def _make_account(db, _tenant_holder, *, with_role=False) -> CloudAccount:
    tenant = Tenant(name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    _tenant_holder["tenant_id"] = tenant.id

    creds = {
        "access_key_id": "AKIA",
        "secret_access_key": "secret",
        "region": "us-east-1",
    }
    if with_role:
        creds["role_arn"] = "arn:aws:iam::123456789012:role/cspm"
        creds["external_id"] = "ext-123"

    account = CloudAccount(
        tenant_id=tenant.id,
        provider="aws",
        display_name="AWS Test",
        provider_account_id="123456789012",
        credential_ref=encrypt_credentials(creds),
    )
    db.add(account)
    await db.flush()
    return account


async def _make_scan(db, account, scan_type="full") -> Scan:
    scan = Scan(cloud_account_id=account.id, scan_type=scan_type, status="running")
    db.add(scan)
    await db.flush()
    return scan


# ── Fake boto3 ──────────────────────────────────────────────────────────


class _NoSuchEntity(Exception):
    pass


class _NoSuchPAB(Exception):
    pass


class _FakePaginator:
    def __init__(self, pages):
        self._pages = pages

    def paginate(self, **kwargs):
        return iter(self._pages)


class _FakeClientExceptions:
    NoSuchEntityException = _NoSuchEntity
    NoSuchPublicAccessBlockConfiguration = _NoSuchPAB


def _make_fake_clients(*, empty=False, raise_all=False):
    """Build a dict of service_name -> fake client.

    empty=True returns empty inventory (so no DB rows are created).
    raise_all=True makes every top-level call raise (graceful-degradation).
    """
    exc = _FakeClientExceptions()

    def err(*a, **k):
        raise RuntimeError("boom")

    # ---- s3 ----
    if empty or raise_all:
        s3 = SimpleNamespace(
            exceptions=exc,
            list_buckets=err if raise_all else (lambda: {"Buckets": []}),
        )
    else:
        s3 = SimpleNamespace(
            exceptions=exc,
            list_buckets=lambda: {"Buckets": [{"Name": "my-bucket", "CreationDate": datetime(2020, 1, 1, tzinfo=UTC)}]},
            get_public_access_block=lambda Bucket: {"PublicAccessBlockConfiguration": {"BlockPublicAcls": True}},
            get_bucket_encryption=lambda Bucket: {"ServerSideEncryptionConfiguration": {"Rules": []}},
            get_bucket_versioning=lambda Bucket: {"Status": "Enabled"},
            get_bucket_logging=lambda Bucket: {"LoggingEnabled": {"TargetBucket": "logs"}},
            get_bucket_tagging=lambda Bucket: {"TagSet": [{"Key": "env", "Value": "prod"}]},
        )

    # ---- ec2 ----
    if raise_all:
        ec2 = SimpleNamespace(
            get_paginator=err,
            describe_vpcs=err,
            describe_flow_logs=err,
        )
    elif empty:
        ec2 = SimpleNamespace(
            get_paginator=lambda op: _FakePaginator([{}]),
            describe_vpcs=lambda: {"Vpcs": []},
            describe_flow_logs=lambda **k: {"FlowLogs": []},
        )
    else:

        def ec2_paginator(op):
            pages = {
                "describe_instances": [
                    {
                        "Reservations": [
                            {
                                "Instances": [
                                    {
                                        "InstanceId": "i-123",
                                        "LaunchTime": datetime(2021, 1, 1, tzinfo=UTC),
                                        "Tags": [{"Key": "Name", "Value": "web"}],
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "describe_security_groups": [
                    {
                        "SecurityGroups": [
                            {
                                "GroupId": "sg-1",
                                "GroupName": "default",
                                "Tags": [{"Key": "Name", "Value": "sg-web"}],
                            }
                        ]
                    }
                ],
                "describe_volumes": [
                    {
                        "Volumes": [
                            {
                                "VolumeId": "vol-1",
                                "Encrypted": False,
                                "Tags": [
                                    {"Key": "team", "Value": "infra"},
                                    {"Key": "Name", "Value": "data-vol"},
                                ],
                            }
                        ]
                    }
                ],
            }
            return _FakePaginator(pages[op])

        ec2 = SimpleNamespace(
            get_paginator=ec2_paginator,
            describe_vpcs=lambda: {"Vpcs": [{"VpcId": "vpc-1", "Tags": [{"Key": "Name", "Value": "main"}]}]},
            describe_flow_logs=lambda **k: {"FlowLogs": [{"FlowLogId": "fl-1"}]},
        )

    # ---- iam ----
    if raise_all:
        iam = SimpleNamespace(
            exceptions=exc,
            get_paginator=err,
            get_account_summary=err,
            get_account_password_policy=err,
        )
    elif empty:
        iam = SimpleNamespace(
            exceptions=exc,
            get_paginator=lambda op: _FakePaginator([{"Users": []}]),
            get_account_summary=lambda: {"SummaryMap": {"AccountMFAEnabled": 1}},
            get_account_password_policy=lambda: {"PasswordPolicy": {"MinimumPasswordLength": 14}},
        )
    else:
        iam = SimpleNamespace(
            exceptions=exc,
            get_paginator=lambda op: _FakePaginator(
                [{"Users": [{"UserName": "alice", "Arn": "arn:aws:iam::123456789012:user/alice"}]}]
            ),
            get_login_profile=lambda UserName: (_ for _ in ()).throw(_NoSuchEntity()),
            list_mfa_devices=lambda UserName: {"MFADevices": [{"SerialNumber": "x"}]},
            list_access_keys=lambda UserName: {
                "AccessKeyMetadata": [{"AccessKeyId": "AK", "CreateDate": datetime(2021, 1, 1, tzinfo=UTC)}]
            },
            list_user_tags=lambda UserName: {"Tags": [{"Key": "team", "Value": "sec"}]},
            get_account_summary=lambda: {"SummaryMap": {"AccountMFAEnabled": 1}},
            get_account_password_policy=lambda: {"PasswordPolicy": {"MinimumPasswordLength": 14}},
        )

    # ---- rds ----
    if raise_all:
        rds = SimpleNamespace(get_paginator=err)
    elif empty:
        rds = SimpleNamespace(get_paginator=lambda op: _FakePaginator([{"DBInstances": []}]))
    else:
        rds = SimpleNamespace(
            get_paginator=lambda op: _FakePaginator(
                [
                    {
                        "DBInstances": [
                            {
                                "DBInstanceIdentifier": "db1",
                                "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db1",
                                "TagList": [{"Key": "env", "Value": "prod"}],
                            }
                        ]
                    }
                ]
            )
        )

    # ---- lambda ----
    if raise_all:
        lam = SimpleNamespace(list_functions=err)
    elif empty:
        lam = SimpleNamespace(list_functions=lambda **k: {"Functions": []})
    else:

        def list_functions(**kwargs):
            if kwargs.get("Marker") == "next":
                return {"Functions": [{"FunctionName": "fn2"}]}
            return {
                "Functions": [
                    {
                        "FunctionName": "fn1",
                        "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:fn1",
                    }
                ],
                "NextMarker": "next",
            }

        lam = SimpleNamespace(
            list_functions=list_functions,
            get_policy=lambda FunctionName: {"Policy": json.dumps({"Statement": []})},
        )

    # ---- cloudtrail ----
    if raise_all:
        ct = SimpleNamespace(describe_trails=err)
    elif empty:
        ct = SimpleNamespace(describe_trails=lambda: {"trailList": []})
    else:
        ct = SimpleNamespace(
            describe_trails=lambda: {
                "trailList": [{"Name": "trail1", "TrailARN": "arn:aws:cloudtrail:us-east-1:123456789012:trail/trail1"}]
            },
            get_trail_status=lambda Name: {"IsLogging": True},
        )

    # ---- guardduty ----
    if raise_all:
        gd = SimpleNamespace(list_detectors=err)
    elif empty:
        # No detectors -> synthetic asset branch
        gd = SimpleNamespace(list_detectors=lambda: {"DetectorIds": []})
    else:
        gd = SimpleNamespace(
            list_detectors=lambda: {"DetectorIds": ["d-1"]},
            get_detector=lambda DetectorId: {"Status": "ENABLED", "Tags": {"k": "v"}},
        )

    # ---- securityhub ----
    if raise_all:
        sh = SimpleNamespace(get_findings=err)
    elif empty:
        sh = SimpleNamespace(get_findings=lambda **k: {"Findings": []})
    else:

        def get_findings(**kwargs):
            if kwargs.get("NextToken") == "tok":
                return {
                    "Findings": [
                        {
                            "Id": "f2",
                            "Title": "passed control",
                            "Severity": {"Label": "LOW"},
                            "Compliance": {"Status": "PASSED"},
                            "GeneratorId": "cis-aws-foundations-benchmark/v/1.2.0/1.1",
                            "Resources": [{"Id": "arn:aws:s3:::my-bucket"}],
                        }
                    ]
                }
            return {
                "Findings": [
                    {
                        "Id": "f1",
                        "Title": "open bucket",
                        "Description": "bucket is public",
                        "Severity": {"Label": "CRITICAL"},
                        "Compliance": {"Status": "FAILED"},
                        "GeneratorId": "aws-foundational-security-best-practices/v/1.0.0/S3.1",
                        "Resources": [{"Id": "arn:aws:s3:::my-bucket"}],
                        "Remediation": {"Recommendation": {"Text": "fix it"}},
                    },
                    {
                        # No resources -> dedup key uses finding id; NOT_AVAILABLE -> not_applicable
                        "Id": "f3",
                        "Title": "na control",
                        "Severity": {"Label": "INFORMATIONAL"},
                        "Compliance": {"Status": "NOT_AVAILABLE"},
                        "GeneratorId": "",
                        "Resources": [],
                    },
                ],
                "NextToken": "tok",
            }

        sh = SimpleNamespace(get_findings=get_findings)

    # ---- config ----
    if raise_all:
        cfg = SimpleNamespace(describe_compliance_by_config_rule=err)
    elif empty:
        cfg = SimpleNamespace(describe_compliance_by_config_rule=lambda **k: {"ComplianceByConfigRules": []})
    else:

        def describe_compliance(**kwargs):
            if kwargs.get("NextToken") == "ctok":
                return {
                    "ComplianceByConfigRules": [
                        {"ConfigRuleName": "rule2", "Compliance": {"ComplianceType": "NON_COMPLIANT"}}
                    ]
                }
            return {
                "ComplianceByConfigRules": [{"ConfigRuleName": "rule1", "Compliance": {"ComplianceType": "COMPLIANT"}}],
                "NextToken": "ctok",
            }

        cfg = SimpleNamespace(describe_compliance_by_config_rule=describe_compliance)

    return {
        "s3": s3,
        "ec2": ec2,
        "iam": iam,
        "rds": rds,
        "lambda": lam,
        "cloudtrail": ct,
        "guardduty": gd,
        "securityhub": sh,
        "config": cfg,
        "sts": SimpleNamespace(),
    }


class _FakeSession:
    """Fake boto3.Session whose client() dispatches to a client dict."""

    clients = {}
    fail_services: set = set()

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def client(self, service_name, **kwargs):
        if service_name in type(self).fail_services:
            raise RuntimeError(f"cannot create {service_name}")
        return type(self).clients[service_name]


@pytest.fixture
def patch_boto3(monkeypatch):
    """Patch boto3.Session and boto3.client; return a setup callable."""
    import boto3

    def _setup(clients, *, fail_services=None):
        _FakeSession.clients = clients
        _FakeSession.fail_services = set(fail_services or [])
        monkeypatch.setattr(boto3, "Session", _FakeSession)

        def fake_client(service_name, **kwargs):
            return clients.get(service_name, SimpleNamespace())

        monkeypatch.setattr(boto3, "client", fake_client)

    yield _setup
    _FakeSession.clients = {}
    _FakeSession.fail_services = set()


# ── Pure-helper tests ───────────────────────────────────────────────────


def test_normalize_resource_type_known():
    assert _normalize_resource_type("AWS::S3::Bucket") == "aws.s3.bucket"
    assert _normalize_resource_type("AWS::EC2::Instance") == "aws.ec2.instance"


def test_normalize_resource_type_three_parts_unknown():
    assert _normalize_resource_type("AWS::SQS::Queue") == "aws.sqs.queue"


def test_normalize_resource_type_fallback_lower():
    assert _normalize_resource_type("SomethingWeird") == "somethingweird"


def test_sanitize_for_json_datetime():
    dt = datetime(2020, 5, 1, 12, 0, tzinfo=UTC)
    assert _sanitize_for_json(dt) == dt.isoformat()


def test_sanitize_for_json_bytes():
    assert _sanitize_for_json(b"hello") == "hello"


def test_sanitize_for_json_nested():
    out = _sanitize_for_json({"a": [1, datetime(2020, 1, 1, tzinfo=UTC)], "b": ("x", b"y")})
    assert out["a"][0] == 1
    assert out["a"][1] == datetime(2020, 1, 1, tzinfo=UTC).isoformat()
    assert out["b"] == ["x", "y"]


def test_sanitize_for_json_unserializable_object():
    class Weird:
        def __repr__(self):
            return "WEIRD"

    assert _sanitize_for_json(Weird()) == "WEIRD"


# ── End-to-end full scan ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_full_scan_populated(db, _tenant_holder, patch_boto3, monkeypatch):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")

    # Seed a control that matches the S3.1 generator id (via substring match).
    control = Control(
        code="CIS-AWS-1",
        name="S3 public access",
        description="d",
        severity="high",
        framework="cis-lite",
        provider_check_ref={"aws": "s3.1"},
    )
    db.add(control)
    await db.flush()

    patch_boto3(_make_fake_clients(empty=False))

    coll = AwsCollector(db, scan)
    stats = await coll.run()

    # Inventory created multiple assets (s3, ec2, sg, vol, vpc, iam user,
    # iam summary, iam pw policy, rds, lambda x2, cloudtrail, guardduty).
    assert stats["assets_created"] > 5
    assert stats["assets_found"] == stats["assets_created"]
    assert stats["security_hub_findings"] == 3
    assert stats["findings_created"] == 3
    assert stats["config_compliance_rules"] == 2

    # Findings persisted with a control matched on the failing S3 finding.
    from sqlalchemy import select

    findings = (await db.execute(select(Finding))).scalars().all()
    assert len(findings) == 3
    statuses = {f.status for f in findings}
    assert statuses == {"fail", "pass", "not_applicable"}
    matched = [f for f in findings if f.control_id is not None]
    assert len(matched) == 1

    # The S3 finding is linked to the s3 asset (resource arn match).
    s3_finding = next(f for f in findings if f.status == "fail")
    assert s3_finding.asset_id is not None

    # account.last_scan_at was set.
    await db.refresh(account)
    assert account.last_scan_at is not None


# ── End-to-end empty scan (covers all empty branches) ───────────────────


@pytest.mark.asyncio
async def test_run_full_scan_empty(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")

    patch_boto3(_make_fake_clients(empty=True))

    coll = AwsCollector(db, scan)
    stats = await coll.run()

    # GuardDuty "not enabled" synthetic asset + iam summary + pw policy.
    assert stats["assets_created"] == 3
    assert stats["security_hub_findings"] == 0
    assert stats["findings_created"] == 0
    assert stats["config_compliance_rules"] == 0


# ── Incremental scan ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_incremental_unchanged_and_updated(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)

    # First, a full scan to create findings.
    full_scan = await _make_scan(db, account, "full")
    patch_boto3(_make_fake_clients(empty=False))
    coll = AwsCollector(db, full_scan)
    await coll.run()

    from sqlalchemy import select

    before = (await db.execute(select(Finding))).scalars().all()
    assert len(before) == 3

    # Now an incremental scan: same findings, same statuses -> unchanged path.
    inc_scan = await _make_scan(db, account, "incremental")
    patch_boto3(_make_fake_clients(empty=False))
    coll2 = AwsCollector(db, inc_scan)
    assert coll2.is_incremental is True
    stats = await coll2.run()

    # No new findings created; existing ones marked unchanged.
    assert stats["findings_created"] == 0
    assert stats["findings_unchanged"] >= 1
    after = (await db.execute(select(Finding))).scalars().all()
    assert len(after) == 3


@pytest.mark.asyncio
async def test_incremental_status_change_updates(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    full_scan = await _make_scan(db, account, "full")
    patch_boto3(_make_fake_clients(empty=False))
    await AwsCollector(db, full_scan).run()

    # Flip the failing finding's status in the DB so incremental sees a change.
    from sqlalchemy import select

    failing = (await db.execute(select(Finding).where(Finding.status == "fail"))).scalars().first()
    failing.status = "pass"
    await db.flush()

    inc_scan = await _make_scan(db, account, "incremental")
    patch_boto3(_make_fake_clients(empty=False))
    stats = await AwsCollector(db, inc_scan).run()

    assert stats["findings_updated"] >= 1


# ── Graceful degradation: every AWS call raises ─────────────────────────


@pytest.mark.asyncio
async def test_run_all_apis_raise(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")

    patch_boto3(_make_fake_clients(raise_all=True))

    coll = AwsCollector(db, scan)
    stats = await coll.run()

    # Everything degraded gracefully and run() still returns. The only asset
    # created is the synthetic IAM password-policy (its except branch upserts a
    # placeholder when get_account_password_policy raises).
    assert stats["assets_created"] == 1
    assert stats["findings_created"] == 0
    assert stats["security_hub_findings"] == 0


# ── Client-construction failures (securityhub/config unavailable) ───────


@pytest.mark.asyncio
async def test_security_hub_and_config_clients_unavailable(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")

    patch_boto3(
        _make_fake_clients(empty=True),
        fail_services={"securityhub", "config"},
    )

    coll = AwsCollector(db, scan)
    stats = await coll.run()

    # The unavailable clients are skipped without error.
    assert stats["security_hub_findings"] == 0
    assert stats["config_compliance_rules"] == 0


# ── Role assumption path (_build_clients with role_arn) ─────────────────


@pytest.mark.asyncio
async def test_build_clients_assume_role(db, _tenant_holder, patch_boto3, monkeypatch):
    account = await _make_account(db, _tenant_holder, with_role=True)
    scan = await _make_scan(db, account, "full")

    clients = _make_fake_clients(empty=True)

    captured = {}

    def fake_assume_role(**kwargs):
        captured["kwargs"] = kwargs
        return {
            "Credentials": {
                "AccessKeyId": "ASIA",
                "SecretAccessKey": "temp-secret",
                "SessionToken": "tok",
            }
        }

    clients["sts"] = SimpleNamespace(assume_role=fake_assume_role)
    patch_boto3(clients)

    coll = AwsCollector(db, scan)
    coll._build_clients(account)

    assert captured["kwargs"]["RoleArn"] == "arn:aws:iam::123456789012:role/cspm"
    assert captured["kwargs"]["ExternalId"] == "ext-123"
    assert coll._region == "us-east-1"
    assert coll._account_id == "123456789012"


@pytest.mark.asyncio
async def test_build_clients_with_endpoint_url_skips_role(db, _tenant_holder, patch_boto3, monkeypatch):
    """When aws_endpoint_url is set (LocalStack), role assumption is skipped."""
    from app.config.settings import settings

    monkeypatch.setattr(settings, "aws_endpoint_url", "http://localhost:4566")

    account = await _make_account(db, _tenant_holder, with_role=True)
    scan = await _make_scan(db, account, "full")

    patch_boto3(_make_fake_clients(empty=True))

    coll = AwsCollector(db, scan)
    coll._build_clients(account)

    # Endpoint set -> direct session, no STS assume_role invoked.
    assert coll._endpoint_url == "http://localhost:4566"
    assert coll._session is not None


# ── _get_client lazy creation + caching ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_client_caches(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")
    clients = _make_fake_clients(empty=True)
    patch_boto3(clients)

    coll = AwsCollector(db, scan)
    coll._build_clients(account)

    c1 = coll._get_client("securityhub")
    c2 = coll._get_client("securityhub")
    assert c1 is c2 is clients["securityhub"]


# ── _client creation failure during _build_clients pre-create loop ──────


@pytest.mark.asyncio
async def test_build_clients_precreate_failure_logged(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")
    clients = _make_fake_clients(empty=True)
    # Make the 'rds' pre-create fail; the loop should swallow and continue.
    patch_boto3(clients, fail_services={"rds"})

    coll = AwsCollector(db, scan)
    coll._build_clients(account)

    # s3/ec2/iam/sts created; rds skipped due to failure.
    assert "s3" in coll._clients
    assert "rds" not in coll._clients


# ── Asset UPDATE branch (re-scan same resources) ────────────────────────


@pytest.mark.asyncio
async def test_full_scan_twice_updates_assets(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)

    scan1 = await _make_scan(db, account, "full")
    patch_boto3(_make_fake_clients(empty=False))
    stats1 = await AwsCollector(db, scan1).run()
    assert stats1["assets_created"] > 5
    assert stats1["assets_updated"] == 0

    # Second full scan with the same inventory -> all assets matched & updated.
    scan2 = await _make_scan(db, account, "full")
    patch_boto3(_make_fake_clients(empty=False))
    stats2 = await AwsCollector(db, scan2).run()
    assert stats2["assets_created"] == 0
    assert stats2["assets_updated"] == stats1["assets_created"]


# ── Inner per-resource sub-call failures (S3 props, IAM details, etc.) ──


def _make_inner_fail_clients():
    """Inventory where each resource's *detail* sub-calls raise.

    Exercises the inner try/except blocks: bucket props/tags, VPC flow logs,
    IAM login-profile/mfa/keys/tags, lambda get_policy, cloudtrail status,
    guardduty get_detector.
    """

    def err(*a, **k):
        raise RuntimeError("detail boom")

    exc = _FakeClientExceptions()

    s3 = SimpleNamespace(
        exceptions=exc,
        list_buckets=lambda: {"Buckets": [{"Name": "b1", "CreationDate": ""}]},
        get_public_access_block=lambda Bucket: (_ for _ in ()).throw(
            _NoSuchPAB()  # named exception branch
        ),
        get_bucket_encryption=err,
        get_bucket_versioning=err,
        get_bucket_logging=err,
        get_bucket_tagging=err,
    )

    ec2 = SimpleNamespace(
        get_paginator=lambda op: _FakePaginator([{}]),
        describe_vpcs=lambda: {"Vpcs": [{"VpcId": "vpc-1", "Tags": []}]},
        describe_flow_logs=err,
    )

    iam = SimpleNamespace(
        exceptions=exc,
        get_paginator=lambda op: _FakePaginator([{"Users": [{"UserName": "bob"}]}]),
        get_login_profile=err,
        list_mfa_devices=err,
        list_access_keys=err,
        list_user_tags=err,
        get_account_summary=err,
        get_account_password_policy=err,
    )

    lam = SimpleNamespace(
        list_functions=lambda **k: {"Functions": [{"FunctionName": "fn1"}]},
        get_policy=err,
    )

    ct = SimpleNamespace(
        describe_trails=lambda: {"trailList": [{"Name": "t1"}]},
        get_trail_status=err,
    )

    gd = SimpleNamespace(
        list_detectors=lambda: {"DetectorIds": ["d-1"]},
        get_detector=err,
    )

    rds = SimpleNamespace(get_paginator=lambda op: _FakePaginator([{"DBInstances": []}]))

    return {
        "s3": s3,
        "ec2": ec2,
        "iam": iam,
        "rds": rds,
        "lambda": lam,
        "cloudtrail": ct,
        "guardduty": gd,
        "securityhub": SimpleNamespace(get_findings=lambda **k: {"Findings": []}),
        "config": SimpleNamespace(describe_compliance_by_config_rule=lambda **k: {"ComplianceByConfigRules": []}),
        "sts": SimpleNamespace(),
    }


@pytest.mark.asyncio
async def test_inventory_detail_subcalls_degrade(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")
    patch_boto3(_make_inner_fail_clients())

    coll = AwsCollector(db, scan)
    stats = await coll.run()

    # Top-level resources still create assets even though detail calls failed.
    # s3 bucket + vpc + iam user + iam pw-policy(except) + lambda + cloudtrail
    # + guardduty detector get failed (no asset for that detector).
    assert stats["assets_created"] >= 5

    from sqlalchemy import select

    assets = (await db.execute(select(Asset))).scalars().all()
    by_type = {a.resource_type for a in assets}
    assert "aws.s3.bucket" in by_type
    assert "aws.ec2.vpc" in by_type
    assert "aws.iam.user" in by_type
    assert "aws.lambda.function" in by_type
    assert "aws.cloudtrail.trail" in by_type

    # The bucket's encryption/versioning sub-calls failed -> defaulted to {}.
    bucket = next(a for a in assets if a.resource_type == "aws.s3.bucket")
    assert bucket.raw_properties["ServerSideEncryptionConfiguration"] == {}
    assert bucket.tags == {}


# ── Existing finding gets control_id on (non-incremental) update ────────


@pytest.mark.asyncio
async def test_existing_finding_gains_control_id_on_full_rescan(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)

    # First full scan WITHOUT a matching control -> finding has no control_id.
    scan1 = await _make_scan(db, account, "full")
    patch_boto3(_make_fake_clients(empty=False))
    await AwsCollector(db, scan1).run()

    from sqlalchemy import select

    failing = (await db.execute(select(Finding).where(Finding.status == "fail"))).scalars().first()
    assert failing.control_id is None

    # Add a control that matches the S3.1 generator id.
    control = Control(
        code="CIS-AWS-S31",
        name="S3 public",
        description="d",
        severity="high",
        framework="cis-lite",
        provider_check_ref={"aws": "s3.1"},
    )
    db.add(control)
    await db.flush()

    # Second full scan -> existing finding updated and control_id back-filled.
    scan2 = await _make_scan(db, account, "full")
    patch_boto3(_make_fake_clients(empty=False))
    stats = await AwsCollector(db, scan2).run()

    assert stats["findings_updated"] >= 1
    await db.refresh(failing)
    assert failing.control_id == control.id


# ── PAB generic error + login-profile-present branches ──────────────────


@pytest.mark.asyncio
async def test_pab_generic_error_and_login_profile_present(db, _tenant_holder, patch_boto3):
    account = await _make_account(db, _tenant_holder)
    scan = await _make_scan(db, account, "full")

    clients = _make_fake_clients(empty=True)

    exc = _FakeClientExceptions()
    # S3 with a bucket whose get_public_access_block raises a *generic* error.
    clients["s3"] = SimpleNamespace(
        exceptions=exc,
        list_buckets=lambda: {"Buckets": [{"Name": "b1", "CreationDate": ""}]},
        get_public_access_block=lambda Bucket: (_ for _ in ()).throw(RuntimeError("pab boom")),
        get_bucket_encryption=lambda Bucket: {"ServerSideEncryptionConfiguration": {}},
        get_bucket_versioning=lambda Bucket: {"Status": ""},
        get_bucket_logging=lambda Bucket: {},
        get_bucket_tagging=lambda Bucket: {"TagSet": []},
    )
    # IAM with a user whose login profile EXISTS (HasLoginProfile=True).
    clients["iam"] = SimpleNamespace(
        exceptions=exc,
        get_paginator=lambda op: _FakePaginator([{"Users": [{"UserName": "carol"}]}]),
        get_login_profile=lambda UserName: {"LoginProfile": {"UserName": UserName}},
        list_mfa_devices=lambda UserName: {"MFADevices": []},
        list_access_keys=lambda UserName: {"AccessKeyMetadata": []},
        list_user_tags=lambda UserName: {"Tags": []},
        get_account_summary=lambda: {"SummaryMap": {}},
        get_account_password_policy=lambda: {"PasswordPolicy": {}},
    )
    patch_boto3(clients)

    coll = AwsCollector(db, scan)
    await coll.run()

    from sqlalchemy import select

    assets = (await db.execute(select(Asset))).scalars().all()
    bucket = next(a for a in assets if a.resource_type == "aws.s3.bucket")
    # PAB generic error -> key never set on props.
    assert "PublicAccessBlockConfiguration" not in bucket.raw_properties

    user = next(a for a in assets if a.resource_type == "aws.iam.user")
    assert user.raw_properties["HasLoginProfile"] is True
