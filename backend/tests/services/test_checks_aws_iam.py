"""Unit tests for AWS IAM checks (CIS-AWS-09, 10, 11, 12)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.models.asset import Asset
from app.services.aws.checks.iam import (
    check_access_key_rotation,
    check_password_policy,
    check_root_mfa,
    check_user_mfa,
)


def _make_asset(resource_type="aws.iam.user", raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"arn:aws:iam::123456789012:{resource_type.split('.')[-1]}/test",
        resource_type=resource_type,
        name="test-iam-resource",
        region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckRootMfa:
    """CIS-AWS-09: Root account must have MFA enabled."""

    def test_pass_when_mfa_enabled(self):
        asset = _make_asset("aws.iam.account-summary", {
            "SummaryMap": {"AccountMFAEnabled": 1}
        })
        result = check_root_mfa(asset)
        assert result.status == "pass"

    def test_fail_when_mfa_disabled(self):
        asset = _make_asset("aws.iam.account-summary", {
            "SummaryMap": {"AccountMFAEnabled": 0}
        })
        result = check_root_mfa(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset("aws.iam.account-summary", {})
        result = check_root_mfa(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset("aws.iam.account-summary", None)
        result = check_root_mfa(asset)
        assert result.status == "fail"


class TestCheckUserMfa:
    """CIS-AWS-10: IAM users with console access must have MFA enabled."""

    def test_pass_when_mfa_enabled(self):
        asset = _make_asset("aws.iam.user", {
            "HasLoginProfile": True,
            "MFADevices": [{"SerialNumber": "arn:aws:iam::123456789012:mfa/user"}],
        })
        result = check_user_mfa(asset)
        assert result.status == "pass"

    def test_fail_when_console_access_no_mfa(self):
        asset = _make_asset("aws.iam.user", {
            "HasLoginProfile": True,
            "MFADevices": [],
        })
        result = check_user_mfa(asset)
        assert result.status == "fail"

    def test_pass_when_no_console_access(self):
        asset = _make_asset("aws.iam.user", {
            "HasLoginProfile": False,
            "MFADevices": [],
        })
        result = check_user_mfa(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset("aws.iam.user", None)
        result = check_user_mfa(asset)
        # No console access (HasLoginProfile defaults to False) -> pass
        assert result.status == "pass"


class TestCheckPasswordPolicy:
    """CIS-AWS-11: IAM password policy must meet CIS requirements."""

    def test_pass_when_compliant(self):
        asset = _make_asset("aws.iam.password-policy", {
            "MinimumPasswordLength": 14,
            "RequireSymbols": True,
            "RequireNumbers": True,
            "RequireUppercaseCharacters": True,
            "RequireLowercaseCharacters": True,
            "MaxPasswordAge": 90,
            "PasswordReusePrevention": 24,
        })
        result = check_password_policy(asset)
        assert result.status == "pass"

    def test_fail_when_short_password(self):
        asset = _make_asset("aws.iam.password-policy", {
            "MinimumPasswordLength": 8,
            "RequireSymbols": True,
            "RequireNumbers": True,
            "RequireUppercaseCharacters": True,
            "RequireLowercaseCharacters": True,
            "MaxPasswordAge": 90,
            "PasswordReusePrevention": 24,
        })
        result = check_password_policy(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset("aws.iam.password-policy", {})
        result = check_password_policy(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset("aws.iam.password-policy", None)
        result = check_password_policy(asset)
        assert result.status == "fail"


class TestCheckAccessKeyRotation:
    """CIS-AWS-12: IAM access keys must be rotated within 90 days."""

    def test_pass_when_key_recent(self):
        recent_date = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        asset = _make_asset("aws.iam.user", {
            "AccessKeys": [{
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "Status": "Active",
                "CreateDate": recent_date,
            }]
        })
        result = check_access_key_rotation(asset)
        assert result.status == "pass"

    def test_fail_when_key_stale(self):
        old_date = (datetime.now(UTC) - timedelta(days=120)).isoformat()
        asset = _make_asset("aws.iam.user", {
            "AccessKeys": [{
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "Status": "Active",
                "CreateDate": old_date,
            }]
        })
        result = check_access_key_rotation(asset)
        assert result.status == "fail"

    def test_pass_when_no_access_keys(self):
        asset = _make_asset("aws.iam.user", {"AccessKeys": []})
        result = check_access_key_rotation(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset("aws.iam.user", None)
        result = check_access_key_rotation(asset)
        assert result.status == "pass"

    def test_pass_when_key_inactive(self):
        old_date = (datetime.now(UTC) - timedelta(days=120)).isoformat()
        asset = _make_asset("aws.iam.user", {
            "AccessKeys": [{
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "Status": "Inactive",
                "CreateDate": old_date,
            }]
        })
        result = check_access_key_rotation(asset)
        assert result.status == "pass"
