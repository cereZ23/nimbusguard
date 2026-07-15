"""Unit tests for the Exchange Online admin client (adminapi InvokeCommand)."""

from __future__ import annotations

import pytest

from app.services.m365 import exchange_client as exchange_module
from app.services.m365.exchange_client import ExchangeAdminClient, ExchangeAdminError

TENANT_GUID = "11111111-2222-3333-4444-555555555555"


class _FakeToken:
    token = "fake-token"


class _FakeCredential:
    raise_on_token = False

    def __init__(self, tenant_id, client_id, client_secret):
        pass

    def get_token(self, scope):
        if type(self).raise_on_token:
            raise RuntimeError("no token")
        return _FakeToken()


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeHttpClient:
    response: _FakeResponse = _FakeResponse(200, {"value": []})
    last_request: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        type(self).last_request = {"url": url, "headers": headers, "json": json}
        return type(self).response


@pytest.fixture(autouse=True)
def _reset_fakes():
    _FakeCredential.raise_on_token = False
    _FakeHttpClient.response = _FakeResponse(200, {"value": []})
    _FakeHttpClient.last_request = {}


@pytest.fixture
def client(monkeypatch) -> ExchangeAdminClient:
    monkeypatch.setattr(exchange_module, "ClientSecretCredential", _FakeCredential)
    monkeypatch.setattr(exchange_module, "create_ssrf_safe_client", lambda timeout=10: _FakeHttpClient())
    c = ExchangeAdminClient(TENANT_GUID, "cid", "secret")
    assert c.authenticate()
    return c


async def test_run_cmdlet_payload_shape(client):
    _FakeHttpClient.response = _FakeResponse(200, {"value": [{"Name": "Default"}]})

    rows = await client.run_cmdlet("Get-TransportRule", {"ResultSize": "Unlimited"})

    assert rows == [{"Name": "Default"}]
    req = _FakeHttpClient.last_request
    assert req["url"] == f"https://outlook.office365.com/adminapi/beta/{TENANT_GUID}/InvokeCommand"
    assert req["json"] == {
        "CmdletInput": {"CmdletName": "Get-TransportRule", "Parameters": {"ResultSize": "Unlimited"}}
    }
    assert req["headers"]["Authorization"] == "Bearer fake-token"


async def test_non_get_cmdlet_rejected(client):
    with pytest.raises(ExchangeAdminError):
        await client.run_cmdlet("Set-TransportRule", {"Identity": "x"})
    # The request never left the client
    assert _FakeHttpClient.last_request == {}


async def test_unauthorized_raises_forbidden(client):
    _FakeHttpClient.response = _FakeResponse(401)

    with pytest.raises(ExchangeAdminError) as exc_info:
        await client.run_cmdlet("Get-OrganizationConfig")

    assert exc_info.value.reason == "exchange_forbidden"
    assert exc_info.value.status_code == 401


async def test_server_error_raises(client):
    _FakeHttpClient.response = _FakeResponse(500)

    with pytest.raises(ExchangeAdminError) as exc_info:
        await client.run_cmdlet("Get-OrganizationConfig")

    assert exc_info.value.reason == "exchange_error"


def test_authenticate_failure(monkeypatch):
    monkeypatch.setattr(exchange_module, "ClientSecretCredential", _FakeCredential)
    _FakeCredential.raise_on_token = True

    client = ExchangeAdminClient(TENANT_GUID, "cid", "secret")

    assert client.authenticate() is False


async def test_run_cmdlet_without_auth_raises():
    client = ExchangeAdminClient(TENANT_GUID, "cid", "secret")
    with pytest.raises(ExchangeAdminError) as exc_info:
        await client.run_cmdlet("Get-OrganizationConfig")
    assert exc_info.value.reason == "exchange_token_failed"
