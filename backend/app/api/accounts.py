from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, AdminUser, CurrentUser
from app.models.cloud_account import CloudAccount
from app.schemas.accounts import (
    CloudAccountCreate,
    CloudAccountResponse,
    CloudAccountUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.schemas.common import ApiResponse, PaginationMeta
from app.services.audit import record_audit
from app.services.credentials import encrypt_credentials

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/test-connection", response_model=ApiResponse[TestConnectionResponse])
async def test_connection(body: TestConnectionRequest, user: AdminUser) -> dict:
    """Validate cloud provider credentials by attempting a simple API call.

    This endpoint is stateless -- credentials are NOT stored.
    Supports both Azure (Resource Graph) and AWS (STS GetCallerIdentity).
    """
    if body.provider == "aws":
        return await _test_aws_connection(body)
    if body.provider == "azure":
        return await _test_azure_connection(body)

    return {
        "data": TestConnectionResponse(
            success=False,
            resource_count=0,
            message=f"Unsupported provider: {body.provider}",
        ),
        "error": None,
        "meta": None,
    }


async def _test_azure_connection(body: TestConnectionRequest) -> dict:
    """Test Azure credentials via Resource Graph query."""
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resourcegraph import ResourceGraphClient
        from azure.mgmt.resourcegraph.models import QueryRequest

        credential = ClientSecretCredential(
            tenant_id=body.tenant_id,
            client_id=body.client_id,
            client_secret=body.client_secret,
        )
        client = ResourceGraphClient(credential)
        query = QueryRequest(
            subscriptions=[body.subscription_id],
            query="Resources | summarize count()",
        )
        result = client.resources(query)
        count = result.data[0]["count_"] if result.data else 0
        logger.info("Azure test connection successful: %d resources found", count)
        return {
            "data": TestConnectionResponse(
                success=True,
                resource_count=count,
                message=f"Connected successfully. Found {count} resources.",
            ),
            "error": None,
            "meta": None,
        }
    except ImportError:
        logger.warning("Azure SDK not installed -- test connection unavailable")
        return {
            "data": TestConnectionResponse(
                success=False,
                resource_count=0,
                message="Azure SDK is not installed on the server.",
            ),
            "error": None,
            "meta": None,
        }
    except Exception as e:
        logger.warning("Azure test connection failed: %s", e)
        return {
            "data": TestConnectionResponse(
                success=False,
                resource_count=0,
                message="Azure connection failed. Check credentials and permissions.",
            ),
            "error": None,
            "meta": None,
        }


async def _test_aws_connection(body: TestConnectionRequest) -> dict:
    """Test AWS credentials via STS GetCallerIdentity."""
    try:
        import boto3

        from app.config.settings import settings

        endpoint_url = settings.aws_endpoint_url or None

        session_kwargs = {
            "aws_access_key_id": body.access_key_id,
            "aws_secret_access_key": body.secret_access_key,
            "region_name": body.region or "us-east-1",
        }
        session = boto3.Session(**session_kwargs)

        # If role_arn is provided, test AssumeRole first
        if body.role_arn and not endpoint_url:
            sts_client = session.client("sts", endpoint_url=endpoint_url)
            assumed = sts_client.assume_role(
                RoleArn=body.role_arn,
                RoleSessionName="cspm-test-connection",
                DurationSeconds=900,
            )
            temp_creds = assumed["Credentials"]
            session = boto3.Session(
                aws_access_key_id=temp_creds["AccessKeyId"],
                aws_secret_access_key=temp_creds["SecretAccessKey"],
                aws_session_token=temp_creds["SessionToken"],
                region_name=body.region or "us-east-1",
            )

        sts_client = session.client("sts", endpoint_url=endpoint_url)
        identity = sts_client.get_caller_identity()
        account_id = identity.get("Account", "")

        # Try a quick S3 list to count resources
        s3_client = session.client("s3", endpoint_url=endpoint_url)
        try:
            buckets = s3_client.list_buckets()
            count = len(buckets.get("Buckets", []))
        except Exception:
            count = 0

        logger.info("AWS test connection successful: account %s, %d S3 buckets", account_id, count)
        return {
            "data": TestConnectionResponse(
                success=True,
                resource_count=count,
                message=f"Connected successfully to account {account_id}. Found {count} S3 buckets.",
            ),
            "error": None,
            "meta": None,
        }
    except ImportError:
        logger.warning("boto3 SDK not installed -- test connection unavailable")
        return {
            "data": TestConnectionResponse(
                success=False,
                resource_count=0,
                message="boto3 SDK is not installed on the server.",
            ),
            "error": None,
            "meta": None,
        }
    except Exception as e:
        logger.warning("AWS test connection failed: %s", e)
        return {
            "data": TestConnectionResponse(
                success=False,
                resource_count=0,
                message="AWS connection failed. Check credentials and permissions.",
            ),
            "error": None,
            "meta": None,
        }


@router.post("", response_model=ApiResponse[CloudAccountResponse], status_code=status.HTTP_201_CREATED)
async def create_account(body: CloudAccountCreate, db: DB, user: AdminUser) -> dict:
    encrypted = encrypt_credentials(body.credentials)

    account = CloudAccount(
        tenant_id=user.tenant_id,
        provider=body.provider,
        display_name=body.display_name,
        provider_account_id=body.provider_account_id,
        credential_ref=encrypted,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="account.create",
        resource_type="cloud_account",
        resource_id=str(account.id),
        detail=f"Created {account.provider} account: {account.display_name}",
    )
    await db.commit()

    logger.info("Cloud account created: %s (%s)", account.display_name, account.provider)
    return {"data": account, "error": None, "meta": None}


@router.get("", response_model=ApiResponse[list[CloudAccountResponse]])
async def list_accounts(
    db: DB,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    from sqlalchemy import func

    query = select(CloudAccount).where(CloudAccount.tenant_id == user.tenant_id)
    total = (
        await db.execute(select(func.count(CloudAccount.id)).where(CloudAccount.tenant_id == user.tenant_id))
    ).scalar() or 0

    result = await db.execute(query.offset((page - 1) * size).limit(size))
    accounts = result.scalars().all()

    return {
        "data": accounts,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.get("/{account_id}", response_model=ApiResponse[CloudAccountResponse])
async def get_account(account_id: uuid.UUID, db: DB, user: CurrentUser) -> dict:
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == account_id,
            CloudAccount.tenant_id == user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return {"data": account, "error": None, "meta": None}


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: uuid.UUID, db: DB, user: AdminUser) -> None:
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == account_id,
            CloudAccount.tenant_id == user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="account.delete",
        resource_type="cloud_account",
        resource_id=str(account_id),
        detail=f"Deleted account: {account.display_name}",
    )
    await db.delete(account)
    await db.commit()
    logger.info("Cloud account deleted: %s", account_id)


@router.put("/{account_id}/schedule", response_model=ApiResponse[CloudAccountResponse])
async def update_schedule(account_id: uuid.UUID, body: CloudAccountUpdate, db: DB, user: AdminUser) -> dict:
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == account_id,
            CloudAccount.tenant_id == user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if body.scan_schedule is not None:
        account.scan_schedule = body.scan_schedule
    if body.display_name is not None:
        account.display_name = body.display_name

    await db.commit()
    await db.refresh(account)

    logger.info("Account %s schedule updated: %s", account_id, account.scan_schedule)
    return {"data": account, "error": None, "meta": None}
