"""AWS CIS-lite check modules.

Importing this package registers all check functions in the global CheckRegistry.
"""
from __future__ import annotations

from app.services.aws.checks import (  # noqa: F401
    cloudtrail,
    ebs,
    ec2,
    guardduty,
    iam,
    lambda_checks,
    rds,
    s3,
    security_group,
    vpc,
)
