"""Unit tests for AWS Security Group checks (CIS-AWS-07, 08)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.security_group import (
    check_rdp_restricted,
    check_ssh_restricted,
)


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:ec2:us-east-1:123456789012:security-group/sg-12345678",
        resource_type="aws.ec2.security-group",
        name="test-sg",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckSshRestricted:
    """CIS-AWS-07: Security groups should not allow unrestricted SSH access."""

    def test_pass_when_ssh_restricted(self):
        asset = _make_asset(
            {
                "IpPermissions": [
                    {
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpProtocol": "tcp",
                        "IpRanges": [{"CidrIp": "10.0.0.0/8"}],
                        "Ipv6Ranges": [],
                    }
                ]
            }
        )
        result = check_ssh_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_ssh_open_ipv4(self):
        asset = _make_asset(
            {
                "IpPermissions": [
                    {
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpProtocol": "tcp",
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        "Ipv6Ranges": [],
                    }
                ]
            }
        )
        result = check_ssh_restricted(asset)
        assert result.status == "fail"

    def test_fail_when_ssh_open_ipv6(self):
        asset = _make_asset(
            {
                "IpPermissions": [
                    {
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpProtocol": "tcp",
                        "IpRanges": [],
                        "Ipv6Ranges": [{"CidrIpv6": "::/0"}],
                    }
                ]
            }
        )
        result = check_ssh_restricted(asset)
        assert result.status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset({})
        result = check_ssh_restricted(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_ssh_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_all_traffic_open(self):
        asset = _make_asset(
            {
                "IpPermissions": [
                    {
                        "FromPort": -1,
                        "ToPort": -1,
                        "IpProtocol": "-1",
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        "Ipv6Ranges": [],
                    }
                ]
            }
        )
        result = check_ssh_restricted(asset)
        assert result.status == "fail"


class TestCheckRdpRestricted:
    """CIS-AWS-08: Security groups should not allow unrestricted RDP access."""

    def test_pass_when_rdp_restricted(self):
        asset = _make_asset(
            {
                "IpPermissions": [
                    {
                        "FromPort": 3389,
                        "ToPort": 3389,
                        "IpProtocol": "tcp",
                        "IpRanges": [{"CidrIp": "192.168.1.0/24"}],
                        "Ipv6Ranges": [],
                    }
                ]
            }
        )
        result = check_rdp_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_rdp_open(self):
        asset = _make_asset(
            {
                "IpPermissions": [
                    {
                        "FromPort": 3389,
                        "ToPort": 3389,
                        "IpProtocol": "tcp",
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        "Ipv6Ranges": [],
                    }
                ]
            }
        )
        result = check_rdp_restricted(asset)
        assert result.status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset({})
        result = check_rdp_restricted(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_rdp_restricted(asset)
        assert result.status == "pass"
