from __future__ import annotations

import logging
from datetime import UTC, datetime

from azure.identity import ClientSecretCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.models.scan import Scan
from app.services.credentials import decrypt_credentials
from app.services.normalizer import build_control_map, match_control

logger = logging.getLogger(__name__)


class AzureCollector:
    def __init__(self, db: AsyncSession, scan: Scan) -> None:
        self.db = db
        self.scan = scan
        self.is_incremental = scan.scan_type == "incremental"
        self.stats = {
            "scan_type": scan.scan_type,
            "assets_found": 0,
            "assets_created": 0,
            "assets_updated": 0,
            "findings_created": 0,
            "findings_updated": 0,
            "findings_unchanged": 0,
        }

    async def run(self) -> dict:
        account = await self._get_account()
        creds = decrypt_credentials(account.credential_ref)
        credential = ClientSecretCredential(
            tenant_id=creds["tenant_id"],
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
        )
        client = ResourceGraphClient(credential)
        subscription_id = account.provider_account_id

        if self.is_incremental:
            # Incremental: skip full inventory, only refresh recommendations
            logger.info("Running incremental scan (skipping inventory)")
            # Still need the asset map for supplementary collections
            self._asset_map = await self._load_asset_map(account.id)
        else:
            await self._collect_inventory(client, subscription_id, account)

        # Supplementary collections (enrich existing assets or add new types)
        await self._collect_flow_logs(client, subscription_id, account)
        await self._collect_activity_log_alerts(client, subscription_id, account)
        await self._collect_role_definitions(client, subscription_id, account)

        await self._collect_secure_score(credential, subscription_id, account)
        await self._collect_recommendations(client, subscription_id, account)

        account.last_scan_at = datetime.now(UTC)
        await self.db.commit()
        return self.stats

    async def _get_account(self) -> CloudAccount:
        result = await self.db.execute(select(CloudAccount).where(CloudAccount.id == self.scan.cloud_account_id))
        account = result.scalar_one()
        return account

    async def _load_asset_map(self, account_id) -> dict[str, Asset]:
        """Pre-load all assets for this account into a provider_id -> Asset map."""
        result = await self.db.execute(select(Asset).where(Asset.cloud_account_id == account_id))
        return {a.provider_id: a for a in result.scalars().all()}

    async def _collect_inventory(
        self, client: ResourceGraphClient, subscription_id: str, account: CloudAccount
    ) -> None:
        # Pre-load existing assets to avoid N+1 queries in the loop
        asset_map = await self._load_asset_map(account.id)

        query = "Resources | project id, name, type, location, tags, properties"
        skip_token = None

        while True:
            request = QueryRequest(
                subscriptions=[subscription_id],
                query=query,
                options={"$skip": 0, "$top": 1000, "$skipToken": skip_token},
            )
            response = client.resources(request)

            for row in response.data:
                self.stats["assets_found"] += 1
                provider_id = row.get("id", "")

                asset = asset_map.get(provider_id)

                if asset:
                    asset.name = row.get("name", asset.name)
                    asset.resource_type = row.get("type", asset.resource_type)
                    asset.region = row.get("location")
                    asset.tags = row.get("tags", {})
                    asset.raw_properties = row.get("properties", {})
                    asset.last_seen_at = datetime.now(UTC)
                    self.stats["assets_updated"] += 1
                else:
                    asset = Asset(
                        cloud_account_id=account.id,
                        provider_id=provider_id,
                        name=row.get("name", ""),
                        resource_type=row.get("type", "unknown"),
                        region=row.get("location"),
                        tags=row.get("tags", {}),
                        raw_properties=row.get("properties", {}),
                    )
                    self.db.add(asset)
                    # Add to map so subsequent pages/collections can find it
                    asset_map[provider_id] = asset
                    self.stats["assets_created"] += 1

            skip_token = response.skip_token
            if not skip_token:
                break

        await self.db.flush()
        # Store the map for use by supplementary collections
        self._asset_map = asset_map
        logger.info(
            "Inventory: %d found, %d created, %d updated",
            self.stats["assets_found"],
            self.stats["assets_created"],
            self.stats["assets_updated"],
        )

    async def _collect_secure_score(
        self, credential: ClientSecretCredential, subscription_id: str, account: CloudAccount
    ) -> None:
        import httpx

        url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            f"/providers/Microsoft.Security/secureScores/ascScore"
            f"?api-version=2020-01-01"
        )

        try:
            from azure.identity import get_bearer_token_provider  # noqa: F401
        except ImportError:
            # Fallback: get token directly
            token = credential.get_token("https://management.azure.com/.default")
            headers = {"Authorization": f"Bearer {token.token}"}

            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                score = data.get("properties", {}).get("score", {})
                current_score = score.get("current")
                max_score = score.get("max")
                if current_score is not None and max_score:
                    pct = round((current_score / max_score) * 100, 1)
                    metadata = dict(account.metadata_ or {})
                    metadata["secure_score"] = pct
                    metadata["secure_score_raw"] = {"current": current_score, "max": max_score}
                    account.metadata_ = metadata
                    logger.info("Secure score: %.1f%%", pct)
            elif response.status_code in (403, 404):
                logger.warning(
                    "Secure score not available (status %d) — Defender may not be enabled",
                    response.status_code,
                )
            else:
                logger.warning("Secure score fetch failed: %d", response.status_code)

    async def _collect_flow_logs(
        self, client: ResourceGraphClient, subscription_id: str, account: CloudAccount
    ) -> None:
        """Query flow logs and patch matching NSG assets with flowLogs data."""
        query = "resources | where type =~ 'microsoft.network/networkwatchers/flowlogs' | project id, name, properties"
        skip_token = None

        while True:
            request = QueryRequest(
                subscriptions=[subscription_id],
                query=query,
                options={"$skip": 0, "$top": 1000, "$skipToken": skip_token},
            )
            response = client.resources(request)

            for row in response.data:
                props = row.get("properties", {})
                target_id = props.get("targetResourceId", "")
                if not target_id:
                    continue

                # Find matching NSG asset from pre-loaded map (no DB query)
                nsg_asset = self._asset_map.get(target_id)
                if nsg_asset and nsg_asset.raw_properties is not None:
                    raw = dict(nsg_asset.raw_properties)
                    flow_logs = raw.get("flowLogs", [])
                    flow_logs.append(
                        {
                            "id": row.get("id"),
                            "enabled": props.get("enabled", False),
                            "retentionPolicy": props.get("retentionPolicy"),
                        }
                    )
                    raw["flowLogs"] = flow_logs
                    nsg_asset.raw_properties = raw

            skip_token = response.skip_token
            if not skip_token:
                break

        await self.db.flush()
        logger.info("Flow logs collection complete")

    async def _collect_activity_log_alerts(
        self, client: ResourceGraphClient, subscription_id: str, account: CloudAccount
    ) -> None:
        """Collect activity log alerts as assets."""
        query = (
            "resources "
            "| where type =~ 'microsoft.insights/activitylogalerts' "
            "| project id, name, type, location, tags, properties"
        )
        skip_token = None

        while True:
            request = QueryRequest(
                subscriptions=[subscription_id],
                query=query,
                options={"$skip": 0, "$top": 1000, "$skipToken": skip_token},
            )
            response = client.resources(request)

            for row in response.data:
                provider_id = row.get("id", "")
                asset = self._asset_map.get(provider_id)

                if asset:
                    asset.raw_properties = row.get("properties", {})
                    asset.last_seen_at = datetime.now(UTC)
                else:
                    asset = Asset(
                        cloud_account_id=account.id,
                        provider_id=provider_id,
                        name=row.get("name", ""),
                        resource_type=row.get("type", "microsoft.insights/activitylogalerts").lower(),
                        region=row.get("location", "global"),
                        tags=row.get("tags", {}),
                        raw_properties=row.get("properties", {}),
                    )
                    self.db.add(asset)
                    self._asset_map[provider_id] = asset

            skip_token = response.skip_token
            if not skip_token:
                break

        await self.db.flush()
        logger.info("Activity log alerts collection complete")

    async def _collect_role_definitions(
        self, client: ResourceGraphClient, subscription_id: str, account: CloudAccount
    ) -> None:
        """Collect custom role definitions as assets."""
        query = (
            "authorizationresources "
            "| where type =~ 'microsoft.authorization/roledefinitions' "
            "| where properties.type == 'CustomRole' "
            "| project id, name, type, properties"
        )
        skip_token = None

        while True:
            request = QueryRequest(
                subscriptions=[subscription_id],
                query=query,
                options={"$skip": 0, "$top": 1000, "$skipToken": skip_token},
            )
            response = client.resources(request)

            for row in response.data:
                provider_id = row.get("id", "")
                asset = self._asset_map.get(provider_id)

                if asset:
                    asset.raw_properties = row.get("properties", {})
                    asset.last_seen_at = datetime.now(UTC)
                else:
                    asset = Asset(
                        cloud_account_id=account.id,
                        provider_id=provider_id,
                        name=row.get("name", ""),
                        resource_type="microsoft.authorization/roledefinitions",
                        region="global",
                        tags={},
                        raw_properties=row.get("properties", {}),
                    )
                    self.db.add(asset)
                    self._asset_map[provider_id] = asset

            skip_token = response.skip_token
            if not skip_token:
                break

        await self.db.flush()
        logger.info("Role definitions collection complete")

    async def _collect_recommendations(
        self, client: ResourceGraphClient, subscription_id: str, account: CloudAccount
    ) -> None:
        # Pre-load control map for normalizing findings
        control_map = await build_control_map(self.db, "azure")

        # Batch-load existing Defender findings for this account to avoid N+1 queries.
        # Defender-sourced findings use the "azure:" dedup_key prefix.
        existing_findings_result = await self.db.execute(
            select(Finding).where(
                Finding.cloud_account_id == account.id,
                Finding.dedup_key.like("azure:%"),
            )
        )
        findings_by_dedup: dict[str, Finding] = {f.dedup_key: f for f in existing_findings_result.scalars().all()}

        query = "securityresources | where type == 'microsoft.security/assessments' | project id, name, properties"
        skip_token = None

        while True:
            request = QueryRequest(
                subscriptions=[subscription_id],
                query=query,
                options={"$skip": 0, "$top": 1000, "$skipToken": skip_token},
            )
            response = client.resources(request)

            for row in response.data:
                props = row.get("properties", {})
                status_obj = props.get("status", {})
                status_code = status_obj.get("code", "").lower()

                if status_code == "healthy":
                    finding_status = "pass"
                elif status_code == "notapplicable":
                    finding_status = "not_applicable"
                else:
                    finding_status = "fail"

                # row["name"] is the Azure assessment UUID
                assessment_id = row.get("name", "")
                resource_id = props.get("resourceDetails", {}).get("Id", row.get("id", ""))
                assessment_name = props.get("displayName", assessment_id)
                dedup_key = f"azure:{resource_id}:{assessment_name}"

                # Normalize: match assessment UUID -> CIS-lite control
                control_id = match_control(assessment_id, control_map)

                # Look up existing finding from pre-loaded map (no DB query)
                finding = findings_by_dedup.get(dedup_key)

                if finding:
                    # Incremental: skip if status hasn't changed
                    if self.is_incremental and finding.status == finding_status:
                        finding.scan_id = self.scan.id
                        finding.last_evaluated_at = datetime.now(UTC)
                        self.stats["findings_unchanged"] += 1
                        continue
                    finding.status = finding_status
                    finding.last_evaluated_at = datetime.now(UTC)
                    finding.scan_id = self.scan.id
                    if control_id and not finding.control_id:
                        finding.control_id = control_id
                    self.stats["findings_updated"] += 1
                else:
                    # Try to match asset from pre-loaded map (no DB query)
                    asset = self._asset_map.get(resource_id)

                    severity = props.get("metadata", {}).get("severity", "medium").lower()
                    if severity not in ("high", "medium", "low"):
                        severity = "medium"

                    finding = Finding(
                        cloud_account_id=account.id,
                        asset_id=asset.id if asset else None,
                        control_id=control_id,
                        scan_id=self.scan.id,
                        status=finding_status,
                        severity=severity,
                        dedup_key=dedup_key,
                        title=assessment_name,
                    )
                    self.db.add(finding)
                    findings_by_dedup[dedup_key] = finding
                    self.stats["findings_created"] += 1

                    # Save evidence with assessment_id for re-normalization
                    evidence = Evidence(
                        finding_id=finding.id,
                        snapshot={**props, "name": assessment_id},
                    )
                    self.db.add(evidence)

            skip_token = response.skip_token
            if not skip_token:
                break

        await self.db.flush()
        logger.info(
            "Recommendations: %d created, %d updated",
            self.stats["findings_created"],
            self.stats["findings_updated"],
        )
