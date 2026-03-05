"""Security Group checks (CIS-AWS-07, 08)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


def _has_unrestricted_ingress(asset: Asset, port: int) -> tuple[bool, dict]:
    """Check if any ingress rule allows access from 0.0.0.0/0 or ::/0 on the given port."""
    props = asset.raw_properties or {}
    ip_permissions = props.get("IpPermissions") or []

    for perm in ip_permissions:
        from_port = perm.get("FromPort", 0)
        to_port = perm.get("ToPort", 0)
        ip_protocol = perm.get("IpProtocol", "")

        # -1 means all traffic
        if ip_protocol == "-1" or (from_port <= port <= to_port):
            # Check IPv4 ranges
            for ip_range in perm.get("IpRanges", []):
                cidr = ip_range.get("CidrIp", "")
                if cidr in ("0.0.0.0/0",):
                    return True, {
                        "rule": {
                            "IpProtocol": ip_protocol,
                            "FromPort": from_port,
                            "ToPort": to_port,
                            "CidrIp": cidr,
                        }
                    }
            # Check IPv6 ranges
            for ip_range in perm.get("Ipv6Ranges", []):
                cidr = ip_range.get("CidrIpv6", "")
                if cidr in ("::/0",):
                    return True, {
                        "rule": {
                            "IpProtocol": ip_protocol,
                            "FromPort": from_port,
                            "ToPort": to_port,
                            "CidrIpv6": cidr,
                        }
                    }

    return False, {}


@check("aws.ec2.security-group", "CIS-AWS-07")
def check_ssh_restricted(asset: Asset) -> EvalResult:
    """CIS-AWS-07: Security groups should not allow unrestricted SSH (port 22)."""
    is_open, evidence = _has_unrestricted_ingress(asset, 22)
    return EvalResult(
        status="fail" if is_open else "pass",
        evidence=evidence if is_open else {"ssh_open_from_internet": False},
        description="SSH (port 22) is open to the internet -- restrict source CIDR"
        if is_open
        else "SSH is not open to the internet",
    )


@check("aws.ec2.security-group", "CIS-AWS-08")
def check_rdp_restricted(asset: Asset) -> EvalResult:
    """CIS-AWS-08: Security groups should not allow unrestricted RDP (port 3389)."""
    is_open, evidence = _has_unrestricted_ingress(asset, 3389)
    return EvalResult(
        status="fail" if is_open else "pass",
        evidence=evidence if is_open else {"rdp_open_from_internet": False},
        description="RDP (port 3389) is open to the internet -- restrict source CIDR"
        if is_open
        else "RDP is not open to the internet",
    )
