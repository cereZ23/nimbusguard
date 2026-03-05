"""Lambda function checks (CIS-AWS-16)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.lambda.function", "CIS-AWS-16")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AWS-16: Lambda functions should not have resource-based policies granting public access."""
    props = asset.raw_properties or {}
    policy = props.get("Policy", {})

    if not policy:
        return EvalResult(
            status="pass",
            evidence={"Policy": None},
            description="No resource-based policy found (no public access)",
        )

    # Check if any statement grants public access
    statements = []
    if isinstance(policy, dict):
        statements = policy.get("Statement", [])
    elif isinstance(policy, str):
        # Policy might be stored as a raw JSON string
        import json

        try:
            parsed = json.loads(policy)
            statements = parsed.get("Statement", [])
        except (json.JSONDecodeError, AttributeError):
            statements = []

    public_statements = []
    for stmt in statements:
        effect = stmt.get("Effect", "")
        principal = stmt.get("Principal", "")
        if effect == "Allow" and principal in ("*", {"AWS": "*"}):
            condition = stmt.get("Condition")
            if not condition:
                public_statements.append(
                    {
                        "Sid": stmt.get("Sid", ""),
                        "Principal": str(principal),
                        "Action": stmt.get("Action", ""),
                    }
                )

    is_public = len(public_statements) > 0
    return EvalResult(
        status="fail" if is_public else "pass",
        evidence={
            "public_statements": public_statements,
            "total_statements": len(statements),
        },
        description=f"{len(public_statements)} statement(s) grant public access"
        if is_public
        else "No public access statements found in policy",
    )
