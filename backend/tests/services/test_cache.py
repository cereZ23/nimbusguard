"""Unit tests for app.services.cache — Redis wrapper.

A minimal in-memory fake Redis stands in for the real client so we can test
hit/miss/serialization and the silent-degradation branches (every public
function swallows Redis errors and must NOT raise).
"""

from __future__ import annotations

import json

import pytest

import app.services.cache as cache_mod
from app.services.cache import (
    DASHBOARD_CACHE_TTL,
    _cache_key,
    cache_get,
    cache_invalidate_pattern,
    cache_invalidate_tenant,
    cache_set,
)


class FakeRedis:
    """Tiny async in-memory Redis supporting the subset cache.py uses."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    async def scan_iter(self, match=None, count=100):
        import fnmatch

        for k in list(self.store.keys()):
            if match is None or fnmatch.fnmatch(k, match):
                yield k


class BrokenRedis:
    """Raises on every operation — exercises the silent-failure branches."""

    async def get(self, key):
        raise ConnectionError("redis down")

    async def set(self, *a, **k):
        raise ConnectionError("redis down")

    async def delete(self, *a, **k):
        raise ConnectionError("redis down")

    def scan_iter(self, *a, **k):
        raise ConnectionError("redis down")


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()

    async def _get_redis():
        return fake

    monkeypatch.setattr(cache_mod, "get_redis", _get_redis)
    return fake


@pytest.fixture
def broken_redis(monkeypatch):
    broken = BrokenRedis()

    async def _get_redis():
        return broken

    monkeypatch.setattr(cache_mod, "get_redis", _get_redis)
    return broken


# ── _cache_key ───────────────────────────────────────────────────────


def test_cache_key_basic():
    assert _cache_key("dashboard:summary", "t1") == "dashboard:summary:t1"


def test_cache_key_sorted_and_skips_none():
    key = _cache_key("p", "t1", zebra="z", alpha="a", skip=None)
    # sorted by key name; None values omitted
    assert key == "p:t1:alpha=a:zebra=z"


# ── get / set round-trip ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_none_on_miss(fake_redis):
    assert await cache_get("missing") is None


@pytest.mark.asyncio
async def test_set_then_get_roundtrip(fake_redis):
    await cache_set("k1", {"a": 1, "b": [1, 2, 3]})
    assert await cache_get("k1") == {"a": 1, "b": [1, 2, 3]}
    assert fake_redis.ttls["k1"] == DASHBOARD_CACHE_TTL


@pytest.mark.asyncio
async def test_set_custom_ttl_and_default_str_serializer(fake_redis):
    import datetime

    # default=str handles non-JSON-native types
    await cache_set("k2", {"ts": datetime.date(2026, 1, 1)}, ttl=99)
    assert fake_redis.ttls["k2"] == 99
    raw = fake_redis.store["k2"]
    assert json.loads(raw)["ts"] == "2026-01-01"


# ── invalidate pattern / tenant ──────────────────────────────────────


@pytest.mark.asyncio
async def test_invalidate_pattern_deletes_matches(fake_redis):
    fake_redis.store.update(
        {
            "dashboard:summary:t1": "1",
            "dashboard:trend:t1:7": "2",
            "other:t1": "3",
        }
    )
    await cache_invalidate_pattern("dashboard:*")
    assert "dashboard:summary:t1" not in fake_redis.store
    assert "dashboard:trend:t1:7" not in fake_redis.store
    assert "other:t1" in fake_redis.store


@pytest.mark.asyncio
async def test_invalidate_pattern_no_matches(fake_redis):
    fake_redis.store["x:y"] = "1"
    await cache_invalidate_pattern("nomatch:*")  # nothing deleted, no error
    assert fake_redis.store["x:y"] == "1"


@pytest.mark.asyncio
async def test_invalidate_tenant_clears_known_and_scanned(fake_redis):
    fake_redis.store.update(
        {
            "dashboard:summary:t1": "a",
            "dashboard:trend:t1": "b",
            "dashboard:compliance-trend:t1": "c",
            "dashboard:cross-cloud:t1": "d",
            "dashboard:trend:t1:30": "e",
            "dashboard:compliance-trend:t1:cis_azure": "f",
            "dashboard:summary:other": "keep",
        }
    )
    await cache_invalidate_tenant("t1")
    # all t1 keys gone
    assert not any(k for k in fake_redis.store if ":t1" in k)
    # other tenant untouched
    assert fake_redis.store["dashboard:summary:other"] == "keep"


# ── silent degradation on Redis errors ───────────────────────────────


@pytest.mark.asyncio
async def test_get_swallows_errors(broken_redis):
    assert await cache_get("k") is None


@pytest.mark.asyncio
async def test_set_swallows_errors(broken_redis):
    await cache_set("k", {"v": 1})  # must not raise


@pytest.mark.asyncio
async def test_invalidate_pattern_swallows_errors(broken_redis):
    await cache_invalidate_pattern("dashboard:*")  # must not raise


@pytest.mark.asyncio
async def test_invalidate_tenant_swallows_errors(broken_redis):
    await cache_invalidate_tenant("t1")  # must not raise


# ── get_redis singleton ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_redis_creates_and_caches_singleton(monkeypatch):
    created = {"n": 0}

    class _Client:
        pass

    def _from_url(url, decode_responses=False):
        created["n"] += 1
        return _Client()

    monkeypatch.setattr(cache_mod.aioredis, "from_url", _from_url)
    monkeypatch.setattr(cache_mod, "_redis", None)

    r1 = await cache_mod.get_redis()
    r2 = await cache_mod.get_redis()
    assert r1 is r2
    assert created["n"] == 1
