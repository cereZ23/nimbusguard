"""Seed demo data for screenshots."""
import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta


async def seed():
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config.settings import settings
    from app.models.asset import Asset
    from app.models.cloud_account import CloudAccount
    from app.models.control import Control
    from app.models.finding import Finding
    from app.models.scan import Scan
    from app.models.user import User

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        user = (await db.execute(select(User).where(User.email == "admin@securekt.com"))).scalar_one()
        tenant_id = user.tenant_id
        print(f"Tenant: {tenant_id}")

        # Create accounts
        azure_acct = CloudAccount(
            tenant_id=tenant_id,
            provider="azure",
            display_name="Azure Production (West Europe)",
            provider_account_id="sub-" + uuid.uuid4().hex[:8],
            credential_ref="mock_encrypted_ref",
            status="active",
        )
        aws_acct = CloudAccount(
            tenant_id=tenant_id,
            provider="aws",
            display_name="AWS Production (us-east-1)",
            provider_account_id="AKIA" + uuid.uuid4().hex[:12].upper(),
            credential_ref="mock_encrypted_ref",
            status="active",
        )
        db.add_all([azure_acct, aws_acct])
        await db.flush()

        # Scans
        now = datetime.now(UTC)
        for acct in [azure_acct, aws_acct]:
            for days_ago in [14, 7, 3, 1, 0]:
                p = random.randint(55, 75)
                f = random.randint(8, 25)
                scan = Scan(
                    cloud_account_id=acct.id,
                    scan_type="full",
                    status="completed",
                    started_at=now - timedelta(days=days_ago, hours=2),
                    finished_at=now - timedelta(days=days_ago, hours=1, minutes=45),
                    stats={"evaluator": {"pass": p, "fail": f, "total": p + f}},
                )
                db.add(scan)
        await db.flush()

        last_scan = (
            await db.execute(select(Scan).where(Scan.status == "completed").order_by(Scan.finished_at.desc()).limit(1))
        ).scalar_one()

        # Controls
        controls = (await db.execute(select(Control).limit(40))).scalars().all()
        print(f"Controls: {len(controls)}")

        # Azure assets
        azure_res = [
            ("Microsoft.Storage/storageAccounts", "stprodwesteu01", "westeurope"),
            ("Microsoft.Storage/storageAccounts", "stprodwesteu02", "westeurope"),
            ("Microsoft.Storage/storageAccounts", "stbackupnortheu", "northeurope"),
            ("Microsoft.Compute/virtualMachines", "vm-web-prod-01", "westeurope"),
            ("Microsoft.Compute/virtualMachines", "vm-web-prod-02", "westeurope"),
            ("Microsoft.Compute/virtualMachines", "vm-api-prod-01", "westeurope"),
            ("Microsoft.Compute/virtualMachines", "vm-db-prod-01", "westeurope"),
            ("Microsoft.Sql/servers", "sql-prod-westeu", "westeurope"),
            ("Microsoft.Sql/servers/databases", "sql-prod-westeu/appdb", "westeurope"),
            ("Microsoft.KeyVault/vaults", "kv-prod-westeu-01", "westeurope"),
            ("Microsoft.KeyVault/vaults", "kv-secrets-prod", "westeurope"),
            ("Microsoft.Web/sites", "app-frontend-prod", "westeurope"),
            ("Microsoft.Web/sites", "app-api-prod", "westeurope"),
            ("Microsoft.Web/sites", "func-processor-prod", "westeurope"),
            ("Microsoft.Network/networkSecurityGroups", "nsg-web-prod", "westeurope"),
            ("Microsoft.Network/networkSecurityGroups", "nsg-db-prod", "westeurope"),
            ("Microsoft.Network/virtualNetworks", "vnet-prod-westeu", "westeurope"),
            ("Microsoft.ContainerRegistry/registries", "crprodwesteu", "westeurope"),
            ("Microsoft.ContainerService/managedClusters", "aks-prod-westeu", "westeurope"),
            ("Microsoft.DocumentDB/databaseAccounts", "cosmos-prod-westeu", "westeurope"),
            ("Microsoft.DBforPostgreSQL/flexibleServers", "pg-prod-westeu", "westeurope"),
            ("Microsoft.Cache/Redis", "redis-prod-westeu", "westeurope"),
            ("Microsoft.Network/publicIPAddresses", "pip-lb-prod", "westeurope"),
            ("Microsoft.Network/applicationGateways", "agw-prod-westeu", "westeurope"),
        ]

        aws_res = [
            ("AWS::S3::Bucket", "s3-app-assets-prod", "us-east-1"),
            ("AWS::S3::Bucket", "s3-logs-prod", "us-east-1"),
            ("AWS::S3::Bucket", "s3-backups-prod", "us-east-1"),
            ("AWS::EC2::Instance", "i-web01-prod", "us-east-1"),
            ("AWS::EC2::Instance", "i-web02-prod", "us-east-1"),
            ("AWS::EC2::Instance", "i-api01-prod", "us-east-1"),
            ("AWS::RDS::DBInstance", "rds-prod-postgres", "us-east-1"),
            ("AWS::RDS::DBInstance", "rds-prod-mysql", "us-east-1"),
            ("AWS::Lambda::Function", "lambda-image-processor", "us-east-1"),
            ("AWS::Lambda::Function", "lambda-auth-handler", "us-east-1"),
            ("AWS::IAM::Role", "role-admin-access", "global"),
            ("AWS::IAM::Role", "role-lambda-exec", "global"),
            ("AWS::EC2::SecurityGroup", "sg-web-prod", "us-east-1"),
            ("AWS::EC2::SecurityGroup", "sg-db-prod", "us-east-1"),
            ("AWS::ECS::Cluster", "ecs-prod-cluster", "us-east-1"),
            ("AWS::ElasticLoadBalancingV2::LoadBalancer", "alb-prod-web", "us-east-1"),
        ]

        all_assets = []
        for rt, name, region in azure_res:
            safe_rt = rt.replace(".", "/")
            asset = Asset(
                cloud_account_id=azure_acct.id,
                provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/rg-prod/{safe_rt}/{name}",
                resource_type=rt,
                name=name,
                region=region,
                first_seen_at=now - timedelta(days=30),
                last_seen_at=now,
            )
            db.add(asset)
            all_assets.append((asset, azure_acct))

        for rt, name, region in aws_res:
            svc = rt.split("::")[1].lower() if "::" in rt else "unknown"
            asset = Asset(
                cloud_account_id=aws_acct.id,
                provider_id=f"arn:aws:{svc}:{region}:123456789012:{name}",
                resource_type=rt,
                name=name,
                region=region,
                first_seen_at=now - timedelta(days=15),
                last_seen_at=now,
            )
            db.add(asset)
            all_assets.append((asset, aws_acct))

        await db.flush()
        print(f"Assets: {len(all_assets)}")

        # Findings
        statuses = ["fail"] * 4 + ["pass"] * 8
        finding_count = 0
        for asset, acct in all_assets:
            used = set()
            for _ in range(random.randint(1, 5)):
                ctrl = random.choice(controls)
                if ctrl.id in used:
                    continue
                used.add(ctrl.id)
                status = random.choice(statuses)
                finding = Finding(
                    cloud_account_id=acct.id,
                    asset_id=asset.id,
                    control_id=ctrl.id,
                    scan_id=last_scan.id,
                    status=status,
                    severity=ctrl.severity or "medium",
                    title=ctrl.name,
                    dedup_key=f"mock:{asset.provider_id}:{ctrl.code}",
                    first_detected_at=now - timedelta(days=random.randint(1, 30)),
                    last_evaluated_at=now,
                )
                db.add(finding)
                finding_count += 1

        await db.flush()

        # Update secure scores
        for acct_obj in [azure_acct, aws_acct]:
            pc = (
                await db.execute(
                    select(func.count(Finding.id)).where(
                        Finding.cloud_account_id == acct_obj.id, Finding.status == "pass"
                    )
                )
            ).scalar() or 0
            tc = (
                await db.execute(
                    select(func.count(Finding.id)).where(Finding.cloud_account_id == acct_obj.id)
                )
            ).scalar() or 0
            score = round(pc / tc * 100, 1) if tc > 0 else 0
            acct_obj.metadata_ = {
                "secure_score": score,
                "secure_score_source": "evaluation_engine",
                "secure_score_details": {"pass": pc, "fail": tc - pc, "total": tc},
            }
            print(f"{acct_obj.display_name}: {score}% ({pc}/{tc})")

        await db.commit()
        print(f"\nDONE: {finding_count} findings, {len(all_assets)} assets, 2 accounts, 10 scans")


asyncio.run(seed())
