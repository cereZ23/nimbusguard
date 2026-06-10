"""Unit tests for app.utils.url_validation — SSRF defense.

These tests monkeypatch socket.getaddrinfo so DNS resolution is fully
controlled and deterministic (no real network). They assert that the
validator BLOCKS internal/reserved addresses and non-http schemes, and
ALLOWS normal public hosts. The SSRF-safe transport is exercised via its
handle_async_request hook by feeding it fake httpx.Request objects.
"""

from __future__ import annotations

import socket

import httpx
import pytest

from app.utils.url_validation import (
    _check_ip_is_public,
    create_ssrf_safe_client,
    validate_public_url,
)


def _fake_getaddrinfo(ip: str):
    """Return a getaddrinfo replacement that always resolves to *ip*."""

    def _inner(host, port, family=0, type=0, proto=0, flags=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _inner


# ── _check_ip_is_public ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # RFC1918
        "172.16.4.4",  # RFC1918
        "192.168.1.1",  # RFC1918
        "169.254.169.254",  # link-local (cloud metadata)
        "::1",  # IPv6 loopback
        "fe80::1",  # IPv6 link-local
        "0.0.0.0",  # reserved/unspecified
    ],
)
def test_check_ip_is_public_blocks_internal(ip):
    with pytest.raises(ValueError):
        _check_ip_is_public(ip)


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"])
def test_check_ip_is_public_allows_public(ip):
    # Should not raise
    _check_ip_is_public(ip)


# ── validate_public_url: scheme enforcement ──────────────────────────


def test_requires_https_by_default():
    with pytest.raises(ValueError, match="https"):
        validate_public_url("http://example.com")


def test_blocks_non_http_scheme_even_when_https_not_required():
    with pytest.raises(ValueError, match="https:// or http://"):
        validate_public_url("ftp://example.com", require_https=False)


def test_allows_http_when_https_not_required(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("8.8.8.8"))
    assert validate_public_url("http://example.com", require_https=False) == "http://example.com"


def test_missing_hostname_raises():
    with pytest.raises(ValueError, match="valid hostname"):
        validate_public_url("https:///path")


# ── validate_public_url: blocked literal hostnames ───────────────────


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "0.0.0.0"])
def test_blocks_literal_loopback_hostnames(host):
    with pytest.raises(ValueError, match="localhost or loopback"):
        validate_public_url(f"https://{host}")


# ── validate_public_url: resolved IP checks ──────────────────────────


@pytest.mark.parametrize(
    "ip",
    ["10.0.0.1", "172.16.0.1", "192.168.0.1", "169.254.169.254", "127.0.0.99"],
)
def test_blocks_when_dns_resolves_to_private(monkeypatch, ip):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(ip))
    with pytest.raises(ValueError, match="private or reserved"):
        validate_public_url("https://evil.example.com")


def test_blocks_ipv4_mapped_ipv6_loopback(monkeypatch):
    # ::ffff:127.0.0.1 is an IPv4-mapped IPv6 address pointing at loopback.
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("::ffff:127.0.0.1"))
    with pytest.raises(ValueError, match="private or reserved"):
        validate_public_url("https://evil.example.com")


def test_allows_public_host(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    assert validate_public_url("https://example.com") == "https://example.com"


def test_unresolvable_host_raises(monkeypatch):
    def _boom(*args, **kwargs):
        raise socket.gaierror("nope")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    with pytest.raises(ValueError, match="Cannot resolve hostname"):
        validate_public_url("https://does-not-exist.example.com")


# ── create_ssrf_safe_client / _SsrfSafeTransport ─────────────────────


def test_create_ssrf_safe_client_config():
    client = create_ssrf_safe_client(timeout=5)
    assert isinstance(client, httpx.AsyncClient)
    assert client.follow_redirects is False


@pytest.mark.asyncio
async def test_transport_blocks_loopback_hostname():
    client = create_ssrf_safe_client()
    transport = client._transport_for_url(httpx.URL("https://localhost/"))
    request = httpx.Request("GET", "https://localhost/path")
    with pytest.raises(httpx.ConnectError, match="blocked hostname"):
        await transport.handle_async_request(request)
    await client.aclose()


@pytest.mark.asyncio
async def test_transport_blocks_private_resolved_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("10.1.2.3"))
    client = create_ssrf_safe_client()
    transport = client._transport_for_url(httpx.URL("https://internal.example.com/"))
    request = httpx.Request("GET", "https://internal.example.com/")
    with pytest.raises(httpx.ConnectError):
        await transport.handle_async_request(request)
    await client.aclose()


@pytest.mark.asyncio
async def test_transport_blocks_unresolvable(monkeypatch):
    def _boom(*args, **kwargs):
        raise socket.gaierror("nope")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    client = create_ssrf_safe_client()
    transport = client._transport_for_url(httpx.URL("https://nope.example.com/"))
    request = httpx.Request("GET", "https://nope.example.com/")
    with pytest.raises(httpx.ConnectError, match="cannot resolve"):
        await transport.handle_async_request(request)
    await client.aclose()


@pytest.mark.asyncio
async def test_transport_allows_public_then_delegates(monkeypatch):
    """A public IP should pass the SSRF gate and delegate to the parent
    transport (which we stub so no real network call is made)."""
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))

    sentinel = httpx.Response(204)
    called = {}

    async def _fake_super(self, request):
        called["url"] = str(request.url)
        return sentinel

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _fake_super)

    client = create_ssrf_safe_client()
    transport = client._transport_for_url(httpx.URL("https://example.com/"))
    request = httpx.Request("GET", "https://example.com/ok")
    resp = await transport.handle_async_request(request)
    assert resp is sentinel
    assert called["url"] == "https://example.com/ok"
    await client.aclose()
