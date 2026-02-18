"""Unit tests for AWS Lambda checks (CIS-AWS-16)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.lambda_checks import check_public_access


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:lambda:us-east-1:123456789012:function:test-function",
        resource_type="aws.lambda.function",
        name="test-function",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckPublicAccess:
    """CIS-AWS-16: Lambda functions should not have public access via resource policy."""

    def test_pass_when_no_policy(self):
        asset = _make_asset({})
        result = check_public_access(asset)
        assert result.status == "pass"

    def test_pass_when_restricted_principal(self):
        asset = _make_asset({
            "Policy": {
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:root"},
                    "Action": "lambda:InvokeFunction",
                }]
            }
        })
        result = check_public_access(asset)
        assert result.status == "pass"

    def test_fail_when_wildcard_principal_no_condition(self):
        asset = _make_asset({
            "Policy": {
                "Statement": [{
                    "Sid": "PublicAccess",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "lambda:InvokeFunction",
                }]
            }
        })
        result = check_public_access(asset)
        assert result.status == "fail"

    def test_pass_when_wildcard_with_condition(self):
        asset = _make_asset({
            "Policy": {
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "lambda:InvokeFunction",
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": "123456789012"
                        }
                    },
                }]
            }
        })
        result = check_public_access(asset)
        assert result.status == "pass"

    def test_fail_when_raw_properties_none(self):
        # None raw_properties -> props = {}, no Policy key -> pass (no policy)
        asset = _make_asset(None)
        result = check_public_access(asset)
        assert result.status == "pass"

    def test_fail_when_aws_wildcard_principal(self):
        asset = _make_asset({
            "Policy": {
                "Statement": [{
                    "Sid": "AwsWildcard",
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": "lambda:InvokeFunction",
                }]
            }
        })
        result = check_public_access(asset)
        assert result.status == "fail"
