"""AWS Collector — collects security data from AWS accounts.

Uses Security Hub, AWS Config, and direct AWS service APIs (S3, EC2, IAM, RDS,
Lambda, etc.) to build an asset inventory and collect security findings.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from functools import partial
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.models.scan import Scan
from app.services.credentials import decrypt_credentials
from app.services.normalizer import build_control_map

logger = logging.getLogger(__name__)

# Severity mapping: Security Hub -> internal
_SEVERITY_MAP = {
    "CRITICAL": "high",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFORMATIONAL": "low",
}

# AWS resource type mapping for readable internal types
_RESOURCE_TYPE_MAP = {
    "AWS::S3::Bucket": "aws.s3.bucket",
    "AWS::EC2::Instance": "aws.ec2.instance",
    "AWS::EC2::SecurityGroup": "aws.ec2.security-group",
    "AWS::EC2::Volume": "aws.ec2.volume",
    "AWS::EC2::VPC": "aws.ec2.vpc",
    "AWS::IAM::User": "aws.iam.user",
    "AWS::RDS::DBInstance": "aws.rds.instance",
    "AWS::Lambda::Function": "aws.lambda.function",
    "AWS::CloudTrail::Trail": "aws.cloudtrail.trail",
    "AWS::GuardDuty::Detector": "aws.guardduty.detector",
}


def _normalize_resource_type(aws_type: str) -> str:
    """Convert AWS resource type to internal format."""
    if aws_type in _RESOURCE_TYPE_MAP:
        return _RESOURCE_TYPE_MAP[aws_type]
    # Fallback: aws.<service>.<resource> from AWS::Service::Resource
    parts = aws_type.split("::")
    if len(parts) == 3:
        return f"aws.{parts[1].lower()}.{parts[2].lower()}"
    return aws_type.lower()


class AwsCollector:
    """Collects security posture data from an AWS account."""

    def __init__(self, db: AsyncSession, scan: Scan) -> None:
        self.db = db
        self.scan = scan
        self.is_incremental = scan.scan_type == "incremental"
        self.stats: dict[str, Any] = {
            "scan_type": scan.scan_type,
            "assets_found": 0,
            "assets_created": 0,
            "assets_updated": 0,
            "findings_created": 0,
            "findings_updated": 0,
            "findings_unchanged": 0,
            "security_hub_findings": 0,
            "config_compliance_rules": 0,
        }
        self._session: Any = None  # boto3 session
        self._clients: dict[str, Any] = {}
        self._asset_map: dict[str, Asset] = {}
        self._region: str = "us-east-1"
        self._account_id: str = ""
        self._loop = asyncio.get_event_loop()

    async def run(self) -> dict:
        """Main entry point -- called by worker task."""
        account = await self._get_account()
        self._build_clients(account)

        if self.is_incremental:
            logger.info("Running incremental AWS scan (skipping full inventory)")
            self._asset_map = await self._load_asset_map(account.id)
        else:
            await self._collect_inventory(account)

        await self._collect_security_hub_findings(account)
        await self._collect_config_compliance(account)

        account.last_scan_at = datetime.now(UTC)
        await self.db.commit()
        return self.stats

    async def _get_account(self) -> CloudAccount:
        result = await self.db.execute(select(CloudAccount).where(CloudAccount.id == self.scan.cloud_account_id))
        return result.scalar_one()

    async def _load_asset_map(self, account_id) -> dict[str, Asset]:
        """Pre-load all assets for this account into a provider_id -> Asset map."""
        result = await self.db.execute(select(Asset).where(Asset.cloud_account_id == account_id))
        return {a.provider_id: a for a in result.scalars().all()}

    def _build_clients(self, account: CloudAccount) -> None:
        """Decrypt credentials and build boto3 clients."""
        import boto3

        creds = decrypt_credentials(account.credential_ref)
        self._region = creds.get("region", "us-east-1")
        self._account_id = account.provider_account_id

        role_arn = creds.get("role_arn")
        external_id = creds.get("external_id")

        if role_arn:
            # Cross-account: assume role via STS
            sts_client = boto3.client(
                "sts",
                aws_access_key_id=creds["access_key_id"],
                aws_secret_access_key=creds["secret_access_key"],
                region_name=self._region,
            )
            assume_kwargs: dict[str, str] = {
                "RoleArn": role_arn,
                "RoleSessionName": "cspm-collector",
                "DurationSeconds": 3600,
            }
            if external_id:
                assume_kwargs["ExternalId"] = external_id

            assumed = sts_client.assume_role(**assume_kwargs)
            temp_creds = assumed["Credentials"]
            self._session = boto3.Session(
                aws_access_key_id=temp_creds["AccessKeyId"],
                aws_secret_access_key=temp_creds["SecretAccessKey"],
                aws_session_token=temp_creds["SessionToken"],
                region_name=self._region,
            )
        else:
            # Direct credentials
            self._session = boto3.Session(
                aws_access_key_id=creds["access_key_id"],
                aws_secret_access_key=creds["secret_access_key"],
                region_name=self._region,
            )

        # Pre-create commonly used clients
        for svc in ("s3", "ec2", "iam", "rds", "sts"):
            try:
                self._clients[svc] = self._session.client(svc)
            except Exception:
                logger.warning("Failed to create %s client", svc, exc_info=True)

    def _get_client(self, service_name: str) -> Any:
        """Get or create a boto3 client for the given service."""
        if service_name not in self._clients:
            self._clients[service_name] = self._session.client(service_name)
        return self._clients[service_name]

    async def _run_sync(self, func, *args, **kwargs):
        """Run a sync boto3 call in a thread executor."""
        return await self._loop.run_in_executor(None, partial(func, *args, **kwargs))

    # ── Inventory Collection ─────────────────────────────────────────

    async def _collect_inventory(self, account: CloudAccount) -> None:
        """Collect asset inventory from AWS APIs."""
        asset_map = await self._load_asset_map(account.id)

        await self._collect_s3_buckets(account, asset_map)
        await self._collect_ec2_instances(account, asset_map)
        await self._collect_security_groups(account, asset_map)
        await self._collect_ebs_volumes(account, asset_map)
        await self._collect_vpcs(account, asset_map)
        await self._collect_iam_users(account, asset_map)
        await self._collect_iam_account_summary(account, asset_map)
        await self._collect_iam_password_policy(account, asset_map)
        await self._collect_rds_instances(account, asset_map)
        await self._collect_lambda_functions(account, asset_map)
        await self._collect_cloudtrail_trails(account, asset_map)
        await self._collect_guardduty_detectors(account, asset_map)

        await self.db.flush()
        self._asset_map = asset_map
        logger.info(
            "AWS Inventory: %d found, %d created, %d updated",
            self.stats["assets_found"],
            self.stats["assets_created"],
            self.stats["assets_updated"],
        )

    def _upsert_asset(
        self,
        account: CloudAccount,
        asset_map: dict[str, Asset],
        provider_id: str,
        name: str,
        resource_type: str,
        region: str | None,
        tags: dict | None,
        raw_properties: dict,
    ) -> Asset:
        """Create or update an asset in the map."""
        self.stats["assets_found"] += 1
        asset = asset_map.get(provider_id)

        if asset:
            asset.name = name
            asset.resource_type = resource_type
            asset.region = region
            asset.tags = tags or {}
            asset.raw_properties = raw_properties
            asset.last_seen_at = datetime.now(UTC)
            self.stats["assets_updated"] += 1
        else:
            asset = Asset(
                cloud_account_id=account.id,
                provider_id=provider_id,
                name=name,
                resource_type=resource_type,
                region=region,
                tags=tags or {},
                raw_properties=raw_properties,
            )
            self.db.add(asset)
            asset_map[provider_id] = asset
            self.stats["assets_created"] += 1

        return asset

    async def _collect_s3_buckets(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect S3 buckets with security-relevant properties."""
        try:
            s3_client = self._get_client("s3")
            response = await self._run_sync(s3_client.list_buckets)
            buckets = response.get("Buckets", [])

            for bucket in buckets:
                bucket_name = bucket.get("Name", "")
                arn = f"arn:aws:s3:::{bucket_name}"
                props: dict[str, Any] = {"Name": bucket_name, "CreationDate": str(bucket.get("CreationDate", ""))}

                # Collect security-relevant properties
                props.update(await self._get_bucket_properties(s3_client, bucket_name))

                self._upsert_asset(
                    account,
                    asset_map,
                    provider_id=arn,
                    name=bucket_name,
                    resource_type="aws.s3.bucket",
                    region=self._region,
                    tags=await self._get_bucket_tags(s3_client, bucket_name),
                    raw_properties=props,
                )

        except Exception:
            logger.warning("Failed to collect S3 buckets", exc_info=True)

    async def _get_bucket_properties(self, s3_client, bucket_name: str) -> dict:
        """Collect security properties for a single S3 bucket."""
        props: dict[str, Any] = {}

        # Public access block
        try:
            pab = await self._run_sync(s3_client.get_public_access_block, Bucket=bucket_name)
            props["PublicAccessBlockConfiguration"] = pab.get("PublicAccessBlockConfiguration", {})
        except s3_client.exceptions.NoSuchPublicAccessBlockConfiguration:
            props["PublicAccessBlockConfiguration"] = {}
        except Exception:
            logger.debug("Could not get public access block for %s", bucket_name)

        # Encryption
        try:
            enc = await self._run_sync(s3_client.get_bucket_encryption, Bucket=bucket_name)
            props["ServerSideEncryptionConfiguration"] = enc.get("ServerSideEncryptionConfiguration", {})
        except Exception:
            props["ServerSideEncryptionConfiguration"] = {}

        # Versioning
        try:
            ver = await self._run_sync(s3_client.get_bucket_versioning, Bucket=bucket_name)
            props["Versioning"] = {"Status": ver.get("Status", "")}
        except Exception:
            props["Versioning"] = {}

        # Logging
        try:
            log = await self._run_sync(s3_client.get_bucket_logging, Bucket=bucket_name)
            props["LoggingEnabled"] = log.get("LoggingEnabled", {})
        except Exception:
            props["LoggingEnabled"] = {}

        return props

    async def _get_bucket_tags(self, s3_client, bucket_name: str) -> dict:
        """Get tags for an S3 bucket."""
        try:
            response = await self._run_sync(s3_client.get_bucket_tagging, Bucket=bucket_name)
            tag_set = response.get("TagSet", [])
            return {tag["Key"]: tag["Value"] for tag in tag_set}
        except Exception:
            return {}

    async def _collect_ec2_instances(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect EC2 instances with pagination."""
        try:
            ec2_client = self._get_client("ec2")
            paginator = ec2_client.get_paginator("describe_instances")

            async for page in self._paginate(paginator):
                for reservation in page.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance.get("InstanceId", "")
                        arn = f"arn:aws:ec2:{self._region}:{self._account_id}:instance/{instance_id}"
                        name = ""
                        tags_dict = {}
                        for tag in instance.get("Tags", []):
                            tags_dict[tag["Key"]] = tag["Value"]
                            if tag["Key"] == "Name":
                                name = tag["Value"]

                        # Sanitize datetimes in properties for JSON serialization
                        props = _sanitize_for_json(instance)

                        self._upsert_asset(
                            account,
                            asset_map,
                            provider_id=arn,
                            name=name or instance_id,
                            resource_type="aws.ec2.instance",
                            region=self._region,
                            tags=tags_dict,
                            raw_properties=props,
                        )

        except Exception:
            logger.warning("Failed to collect EC2 instances", exc_info=True)

    async def _collect_security_groups(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect EC2 security groups."""
        try:
            ec2_client = self._get_client("ec2")
            paginator = ec2_client.get_paginator("describe_security_groups")

            async for page in self._paginate(paginator):
                for sg in page.get("SecurityGroups", []):
                    sg_id = sg.get("GroupId", "")
                    arn = f"arn:aws:ec2:{self._region}:{self._account_id}:security-group/{sg_id}"
                    tags_dict = {}
                    name = sg.get("GroupName", sg_id)
                    for tag in sg.get("Tags", []):
                        tags_dict[tag["Key"]] = tag["Value"]
                        if tag["Key"] == "Name":
                            name = tag["Value"]

                    self._upsert_asset(
                        account,
                        asset_map,
                        provider_id=arn,
                        name=name,
                        resource_type="aws.ec2.security-group",
                        region=self._region,
                        tags=tags_dict,
                        raw_properties=_sanitize_for_json(sg),
                    )

        except Exception:
            logger.warning("Failed to collect security groups", exc_info=True)

    async def _collect_ebs_volumes(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect EBS volumes."""
        try:
            ec2_client = self._get_client("ec2")
            paginator = ec2_client.get_paginator("describe_volumes")

            async for page in self._paginate(paginator):
                for vol in page.get("Volumes", []):
                    vol_id = vol.get("VolumeId", "")
                    arn = f"arn:aws:ec2:{self._region}:{self._account_id}:volume/{vol_id}"
                    tags_dict = {}
                    name = vol_id
                    for tag in vol.get("Tags", []):
                        tags_dict[tag["Key"]] = tag["Value"]
                        if tag["Key"] == "Name":
                            name = tag["Value"]

                    self._upsert_asset(
                        account,
                        asset_map,
                        provider_id=arn,
                        name=name,
                        resource_type="aws.ec2.volume",
                        region=self._region,
                        tags=tags_dict,
                        raw_properties=_sanitize_for_json(vol),
                    )

        except Exception:
            logger.warning("Failed to collect EBS volumes", exc_info=True)

    async def _collect_vpcs(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect VPCs with flow log status."""
        try:
            ec2_client = self._get_client("ec2")
            response = await self._run_sync(ec2_client.describe_vpcs)

            for vpc in response.get("Vpcs", []):
                vpc_id = vpc.get("VpcId", "")
                arn = f"arn:aws:ec2:{self._region}:{self._account_id}:vpc/{vpc_id}"
                tags_dict = {}
                name = vpc_id
                for tag in vpc.get("Tags", []):
                    tags_dict[tag["Key"]] = tag["Value"]
                    if tag["Key"] == "Name":
                        name = tag["Value"]

                props = _sanitize_for_json(vpc)

                # Collect flow logs for this VPC
                try:
                    fl_response = await self._run_sync(
                        ec2_client.describe_flow_logs,
                        Filters=[{"Name": "resource-id", "Values": [vpc_id]}],
                    )
                    props["FlowLogs"] = _sanitize_for_json(fl_response.get("FlowLogs", []))
                except Exception:
                    props["FlowLogs"] = []

                self._upsert_asset(
                    account,
                    asset_map,
                    provider_id=arn,
                    name=name,
                    resource_type="aws.ec2.vpc",
                    region=self._region,
                    tags=tags_dict,
                    raw_properties=props,
                )

        except Exception:
            logger.warning("Failed to collect VPCs", exc_info=True)

    async def _collect_iam_users(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect IAM users with security-relevant properties."""
        try:
            iam_client = self._get_client("iam")
            paginator = iam_client.get_paginator("list_users")

            async for page in self._paginate(paginator):
                for user in page.get("Users", []):
                    user_name = user.get("UserName", "")
                    arn = user.get("Arn", f"arn:aws:iam::{self._account_id}:user/{user_name}")
                    props = _sanitize_for_json(user)

                    # Check for login profile (console access)
                    try:
                        await self._run_sync(iam_client.get_login_profile, UserName=user_name)
                        props["HasLoginProfile"] = True
                    except iam_client.exceptions.NoSuchEntityException:
                        props["HasLoginProfile"] = False
                    except Exception:
                        props["HasLoginProfile"] = False

                    # List MFA devices
                    try:
                        mfa_response = await self._run_sync(iam_client.list_mfa_devices, UserName=user_name)
                        props["MFADevices"] = _sanitize_for_json(mfa_response.get("MFADevices", []))
                    except Exception:
                        props["MFADevices"] = []

                    # List access keys
                    try:
                        ak_response = await self._run_sync(iam_client.list_access_keys, UserName=user_name)
                        props["AccessKeys"] = _sanitize_for_json(ak_response.get("AccessKeyMetadata", []))
                    except Exception:
                        props["AccessKeys"] = []

                    # Get user tags
                    tags_dict = {}
                    try:
                        tags_response = await self._run_sync(iam_client.list_user_tags, UserName=user_name)
                        for tag in tags_response.get("Tags", []):
                            tags_dict[tag["Key"]] = tag["Value"]
                    except Exception:
                        pass

                    self._upsert_asset(
                        account,
                        asset_map,
                        provider_id=arn,
                        name=user_name,
                        resource_type="aws.iam.user",
                        region="global",
                        tags=tags_dict,
                        raw_properties=props,
                    )

        except Exception:
            logger.warning("Failed to collect IAM users", exc_info=True)

    async def _collect_iam_account_summary(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect IAM account summary (for root MFA check)."""
        try:
            iam_client = self._get_client("iam")
            response = await self._run_sync(iam_client.get_account_summary)
            summary = response.get("SummaryMap", {})

            arn = f"arn:aws:iam::{self._account_id}:account-summary"
            self._upsert_asset(
                account,
                asset_map,
                provider_id=arn,
                name="IAM Account Summary",
                resource_type="aws.iam.account-summary",
                region="global",
                tags={},
                raw_properties={"SummaryMap": summary},
            )
        except Exception:
            logger.warning("Failed to collect IAM account summary", exc_info=True)

    async def _collect_iam_password_policy(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect IAM password policy."""
        try:
            iam_client = self._get_client("iam")
            response = await self._run_sync(iam_client.get_account_password_policy)
            policy = response.get("PasswordPolicy", {})

            arn = f"arn:aws:iam::{self._account_id}:password-policy"
            self._upsert_asset(
                account,
                asset_map,
                provider_id=arn,
                name="IAM Password Policy",
                resource_type="aws.iam.password-policy",
                region="global",
                tags={},
                raw_properties=_sanitize_for_json(policy),
            )
        except Exception:
            # NoSuchEntityException means no custom policy exists
            logger.info("No custom IAM password policy found (or permission denied)")
            arn = f"arn:aws:iam::{self._account_id}:password-policy"
            self._upsert_asset(
                account,
                asset_map,
                provider_id=arn,
                name="IAM Password Policy",
                resource_type="aws.iam.password-policy",
                region="global",
                tags={},
                raw_properties={
                    "MinimumPasswordLength": 0,
                    "RequireSymbols": False,
                    "RequireNumbers": False,
                    "RequireUppercaseCharacters": False,
                    "RequireLowercaseCharacters": False,
                    "MaxPasswordAge": 0,
                    "PasswordReusePrevention": 0,
                    "_note": "No custom password policy found",
                },
            )

    async def _collect_rds_instances(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect RDS DB instances."""
        try:
            rds_client = self._get_client("rds")
            paginator = rds_client.get_paginator("describe_db_instances")

            async for page in self._paginate(paginator):
                for db_instance in page.get("DBInstances", []):
                    db_id = db_instance.get("DBInstanceIdentifier", "")
                    arn = db_instance.get(
                        "DBInstanceArn",
                        f"arn:aws:rds:{self._region}:{self._account_id}:db:{db_id}",
                    )

                    tags_dict = {}
                    for tag in db_instance.get("TagList", []):
                        tags_dict[tag["Key"]] = tag["Value"]

                    self._upsert_asset(
                        account,
                        asset_map,
                        provider_id=arn,
                        name=db_id,
                        resource_type="aws.rds.instance",
                        region=self._region,
                        tags=tags_dict,
                        raw_properties=_sanitize_for_json(db_instance),
                    )

        except Exception:
            logger.warning("Failed to collect RDS instances", exc_info=True)

    async def _collect_lambda_functions(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect Lambda functions."""
        try:
            lambda_client = self._get_client("lambda")
            kwargs: dict[str, Any] = {}
            while True:
                response = await self._run_sync(lambda_client.list_functions, **kwargs)

                for func in response.get("Functions", []):
                    func_name = func.get("FunctionName", "")
                    arn = func.get(
                        "FunctionArn",
                        f"arn:aws:lambda:{self._region}:{self._account_id}:function:{func_name}",
                    )

                    props = _sanitize_for_json(func)

                    # Get resource policy
                    try:
                        policy_response = await self._run_sync(lambda_client.get_policy, FunctionName=func_name)
                        policy_str = policy_response.get("Policy", "")
                        if policy_str:
                            props["Policy"] = json.loads(policy_str)
                    except Exception:
                        props["Policy"] = {}

                    # Get tags
                    tags_dict = func.get("Tags", {}) or {}

                    self._upsert_asset(
                        account,
                        asset_map,
                        provider_id=arn,
                        name=func_name,
                        resource_type="aws.lambda.function",
                        region=self._region,
                        tags=tags_dict,
                        raw_properties=props,
                    )

                next_marker = response.get("NextMarker")
                if not next_marker:
                    break
                kwargs["Marker"] = next_marker

        except Exception:
            logger.warning("Failed to collect Lambda functions", exc_info=True)

    async def _collect_cloudtrail_trails(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect CloudTrail trails."""
        try:
            ct_client = self._get_client("cloudtrail")
            response = await self._run_sync(ct_client.describe_trails)

            for trail in response.get("trailList", []):
                trail_name = trail.get("Name", "")
                arn = trail.get(
                    "TrailARN",
                    f"arn:aws:cloudtrail:{self._region}:{self._account_id}:trail/{trail_name}",
                )

                props = _sanitize_for_json(trail)

                # Get trail status (is it logging?)
                try:
                    status_response = await self._run_sync(ct_client.get_trail_status, Name=arn)
                    props["IsLogging"] = status_response.get("IsLogging", False)
                except Exception:
                    props["IsLogging"] = False

                self._upsert_asset(
                    account,
                    asset_map,
                    provider_id=arn,
                    name=trail_name,
                    resource_type="aws.cloudtrail.trail",
                    region=self._region,
                    tags={},
                    raw_properties=props,
                )

        except Exception:
            logger.warning("Failed to collect CloudTrail trails", exc_info=True)

    async def _collect_guardduty_detectors(self, account: CloudAccount, asset_map: dict[str, Asset]) -> None:
        """Collect GuardDuty detectors."""
        try:
            gd_client = self._get_client("guardduty")
            response = await self._run_sync(gd_client.list_detectors)
            detector_ids = response.get("DetectorIds", [])

            if not detector_ids:
                # Create a synthetic asset representing "no GuardDuty"
                arn = f"arn:aws:guardduty:{self._region}:{self._account_id}:detector/none"
                self._upsert_asset(
                    account,
                    asset_map,
                    provider_id=arn,
                    name="GuardDuty (not enabled)",
                    resource_type="aws.guardduty.detector",
                    region=self._region,
                    tags={},
                    raw_properties={"Status": "NOT_FOUND", "DetectorId": ""},
                )
                return

            for detector_id in detector_ids:
                try:
                    detector = await self._run_sync(gd_client.get_detector, DetectorId=detector_id)
                    arn = f"arn:aws:guardduty:{self._region}:{self._account_id}:detector/{detector_id}"
                    props = _sanitize_for_json(detector)
                    props["DetectorId"] = detector_id

                    self._upsert_asset(
                        account,
                        asset_map,
                        provider_id=arn,
                        name=f"GuardDuty Detector {detector_id}",
                        resource_type="aws.guardduty.detector",
                        region=self._region,
                        tags=detector.get("Tags", {}),
                        raw_properties=props,
                    )
                except Exception:
                    logger.warning("Failed to get GuardDuty detector %s", detector_id, exc_info=True)

        except Exception:
            logger.warning("Failed to collect GuardDuty detectors", exc_info=True)

    # ── Security Hub Findings ────────────────────────────────────────

    async def _collect_security_hub_findings(self, account: CloudAccount) -> None:
        """Collect findings from AWS Security Hub."""
        try:
            sh_client = self._get_client("securityhub")
        except Exception:
            logger.info("Security Hub client not available, skipping")
            return

        control_map = await build_control_map(self.db, "aws")

        # Batch-load existing AWS findings for this account
        existing_findings_result = await self.db.execute(
            select(Finding).where(
                Finding.cloud_account_id == account.id,
                Finding.dedup_key.like("aws:%"),
            )
        )
        findings_by_dedup: dict[str, Finding] = {f.dedup_key: f for f in existing_findings_result.scalars().all()}

        filters = {
            "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
            "WorkflowStatus": [
                {"Value": "NEW", "Comparison": "EQUALS"},
                {"Value": "NOTIFIED", "Comparison": "EQUALS"},
            ],
        }

        try:
            next_token = None
            while True:
                kwargs: dict[str, Any] = {
                    "Filters": filters,
                    "MaxResults": 100,
                }
                if next_token:
                    kwargs["NextToken"] = next_token

                response = await self._run_sync(sh_client.get_findings, **kwargs)

                for sh_finding in response.get("Findings", []):
                    self.stats["security_hub_findings"] += 1
                    self._process_security_hub_finding(sh_finding, account, control_map, findings_by_dedup)

                next_token = response.get("NextToken")
                if not next_token:
                    break

            await self.db.flush()
            logger.info(
                "Security Hub: %d findings processed, %d created, %d updated",
                self.stats["security_hub_findings"],
                self.stats["findings_created"],
                self.stats["findings_updated"],
            )

        except Exception:
            logger.warning("Failed to collect Security Hub findings", exc_info=True)

    def _process_security_hub_finding(
        self,
        sh_finding: dict,
        account: CloudAccount,
        control_map: dict,
        findings_by_dedup: dict[str, Finding],
    ) -> None:
        """Process a single Security Hub finding."""
        finding_id = sh_finding.get("Id", "")
        title = sh_finding.get("Title", "")
        severity_label = sh_finding.get("Severity", {}).get("Label", "MEDIUM").upper()
        severity = _SEVERITY_MAP.get(severity_label, "medium")

        # Determine status
        compliance = sh_finding.get("Compliance", {})
        compliance_status = compliance.get("Status", "").upper()
        if compliance_status == "PASSED":
            finding_status = "pass"
        elif compliance_status == "NOT_AVAILABLE":
            finding_status = "not_applicable"
        else:
            finding_status = "fail"

        # Get resource ARN
        resources = sh_finding.get("Resources", [])
        resource_arn = resources[0].get("Id", "") if resources else ""

        # Build dedup key
        # Use generator control ID if available, otherwise use finding ID
        generator_id = sh_finding.get("GeneratorId", "")
        dedup_key = f"aws:{resource_arn}:{generator_id}" if resource_arn else f"aws:{finding_id}"

        # Normalize: try to match to a CIS-lite control
        control_id = None
        # Try matching by generator_id (often maps to AWS Config rule or Security Hub control)
        for ref_key, ctrl_id in control_map.items():
            if ref_key in generator_id.lower():
                control_id = ctrl_id
                break

        finding = findings_by_dedup.get(dedup_key)

        if finding:
            if self.is_incremental and finding.status == finding_status:
                finding.scan_id = self.scan.id
                finding.last_evaluated_at = datetime.now(UTC)
                self.stats["findings_unchanged"] += 1
                return
            finding.status = finding_status
            finding.last_evaluated_at = datetime.now(UTC)
            finding.scan_id = self.scan.id
            if control_id and not finding.control_id:
                finding.control_id = control_id
            self.stats["findings_updated"] += 1
        else:
            # Try to link to an asset
            asset = self._asset_map.get(resource_arn)

            finding = Finding(
                cloud_account_id=account.id,
                asset_id=asset.id if asset else None,
                control_id=control_id,
                scan_id=self.scan.id,
                status=finding_status,
                severity=severity,
                dedup_key=dedup_key,
                title=title,
            )
            self.db.add(finding)
            findings_by_dedup[dedup_key] = finding
            self.stats["findings_created"] += 1

            # Save evidence
            evidence = Evidence(
                finding_id=finding.id,
                snapshot={
                    "source": "security_hub",
                    "finding_id": finding_id,
                    "generator_id": generator_id,
                    "title": title,
                    "severity": severity_label,
                    "compliance_status": compliance_status,
                    "resource_arn": resource_arn,
                    "description": sh_finding.get("Description", ""),
                    "remediation": sh_finding.get("Remediation", {}),
                },
            )
            self.db.add(evidence)

    # ── AWS Config Compliance ────────────────────────────────────────

    async def _collect_config_compliance(self, account: CloudAccount) -> None:
        """Collect compliance data from AWS Config rules."""
        try:
            config_client = self._get_client("config")
        except Exception:
            logger.info("AWS Config client not available, skipping")
            return

        try:
            # Get all Config rules and their compliance
            next_token = None
            while True:
                kwargs: dict[str, Any] = {}
                if next_token:
                    kwargs["NextToken"] = next_token

                response = await self._run_sync(config_client.describe_compliance_by_config_rule, **kwargs)

                for rule_compliance in response.get("ComplianceByConfigRules", []):
                    self.stats["config_compliance_rules"] += 1
                    rule_name = rule_compliance.get("ConfigRuleName", "")
                    compliance = rule_compliance.get("Compliance", {})
                    compliance_type = compliance.get("ComplianceType", "")

                    logger.debug("Config rule %s: %s", rule_name, compliance_type)

                next_token = response.get("NextToken")
                if not next_token:
                    break

            logger.info(
                "AWS Config: %d compliance rules processed",
                self.stats["config_compliance_rules"],
            )

        except Exception:
            logger.warning("Failed to collect AWS Config compliance", exc_info=True)

    # ── Pagination Helper ────────────────────────────────────────────

    async def _paginate(self, paginator, **kwargs):
        """Async generator wrapping a boto3 paginator."""
        page_iterator = paginator.paginate(**kwargs)
        for page in page_iterator:
            yield page
            # Yield control back to the event loop between pages
            await asyncio.sleep(0)


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize an object for JSON serialization.

    Converts datetime objects to ISO strings, handles bytes, etc.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    # boto3 sometimes returns special types
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
