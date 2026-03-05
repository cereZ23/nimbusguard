"""SCIM 2.0 request/response schemas (RFC 7643 / RFC 7644)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── SCIM Name sub-resource ────────────────────────────────────────────


class ScimName(BaseModel):
    formatted: str | None = None
    familyName: str | None = None
    givenName: str | None = None


# ── SCIM Email sub-resource ───────────────────────────────────────────


class ScimEmail(BaseModel):
    value: str
    type: str | None = "work"
    primary: bool = True


# ── SCIM Meta ─────────────────────────────────────────────────────────


class ScimMeta(BaseModel):
    resourceType: str = "User"
    created: str | None = None
    lastModified: str | None = None
    location: str | None = None


# ── SCIM User resource ───────────────────────────────────────────────


class ScimUser(BaseModel):
    """SCIM 2.0 User resource representation."""

    schemas: list[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:User"])
    id: str | None = None
    externalId: str | None = None
    userName: str
    name: ScimName | None = None
    displayName: str | None = None
    emails: list[ScimEmail] | None = None
    active: bool = True
    meta: ScimMeta | None = None


# ── SCIM List Response ────────────────────────────────────────────────


class ScimListResponse(BaseModel):
    """SCIM 2.0 ListResponse (RFC 7644 Section 3.4.2)."""

    schemas: list[str] = Field(default=["urn:ietf:params:scim:api:messages:2.0:ListResponse"])
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int = 20
    Resources: list[dict[str, Any]] = Field(default_factory=list)


# ── SCIM Patch Operation ─────────────────────────────────────────────


class ScimPatchOp(BaseModel):
    """A single SCIM Patch operation."""

    op: str  # "add", "replace", "remove"
    path: str | None = None
    value: Any | None = None


class ScimPatchRequest(BaseModel):
    """SCIM 2.0 Patch request body (RFC 7644 Section 3.5.2)."""

    schemas: list[str] = Field(default=["urn:ietf:params:scim:api:messages:2.0:PatchOp"])
    Operations: list[ScimPatchOp]


# ── SCIM Error ────────────────────────────────────────────────────────


class ScimError(BaseModel):
    """SCIM 2.0 error response (RFC 7644 Section 3.12)."""

    schemas: list[str] = Field(default=["urn:ietf:params:scim:api:messages:2.0:Error"])
    status: str
    detail: str | None = None
    scimType: str | None = None


# ── SCIM Service Provider Config ──────────────────────────────────────


class ScimBulkConfig(BaseModel):
    supported: bool = False
    maxOperations: int = 0
    maxPayloadSize: int = 0


class ScimFilterConfig(BaseModel):
    supported: bool = True
    maxResults: int = 200


class ScimChangePasswordConfig(BaseModel):
    supported: bool = False


class ScimSortConfig(BaseModel):
    supported: bool = False


class ScimETagConfig(BaseModel):
    supported: bool = False


class ScimPatchConfig(BaseModel):
    supported: bool = True


class ScimAuthScheme(BaseModel):
    type: str = "oauthbearertoken"
    name: str = "OAuth Bearer Token"
    description: str = "Authentication scheme using a SCIM bearer token"


class ScimServiceProviderConfig(BaseModel):
    schemas: list[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"])
    documentationUri: str | None = None
    patch: ScimPatchConfig = Field(default_factory=ScimPatchConfig)
    bulk: ScimBulkConfig = Field(default_factory=ScimBulkConfig)
    filter: ScimFilterConfig = Field(default_factory=ScimFilterConfig)
    changePassword: ScimChangePasswordConfig = Field(default_factory=ScimChangePasswordConfig)
    sort: ScimSortConfig = Field(default_factory=ScimSortConfig)
    etag: ScimETagConfig = Field(default_factory=ScimETagConfig)
    authenticationSchemes: list[ScimAuthScheme] = Field(default_factory=lambda: [ScimAuthScheme()])


# ── SCIM Schema ───────────────────────────────────────────────────────


class ScimSchemaAttribute(BaseModel):
    name: str
    type: str
    multiValued: bool = False
    required: bool = False
    mutability: str = "readWrite"
    returned: str = "default"
    uniqueness: str = "none"
    description: str = ""


class ScimSchema(BaseModel):
    schemas: list[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:Schema"])
    id: str
    name: str
    description: str = ""
    attributes: list[ScimSchemaAttribute] = Field(default_factory=list)


# ── SCIM Resource Type ────────────────────────────────────────────────


class ScimSchemaExtension(BaseModel):
    schema_: str = Field(alias="schema")
    required: bool = True

    model_config = {"populate_by_name": True}


class ScimResourceType(BaseModel):
    schemas: list[str] = Field(default=["urn:ietf:params:scim:schemas:core:2.0:ResourceType"])
    id: str = "User"
    name: str = "User"
    description: str = "User Account"
    endpoint: str = "/scim/v2/Users"
    schema_: str = Field(
        default="urn:ietf:params:scim:schemas:core:2.0:User",
        alias="schema",
    )
    schemaExtensions: list[ScimSchemaExtension] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
