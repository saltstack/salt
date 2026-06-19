"""
Unit tests for the redis_cache cache module.

Regression tests for bugs fixed in PR #67814:
- _build_bank_hier() was adding "." instead of the child bank name to the bank
  hierarchy, causing manage.* runners to return empty minion lists.
- list_() was querying the wrong Redis key (bank-keys set instead of bank set),
  so listing sub-banks (e.g. minion IDs under "minions") always returned [].
"""

import logging

import pytest

import salt.cache.redis_cache as redis_cache

log = logging.getLogger(__name__)


class MockRedisPipeline:
    """
    Thin pipeline wrapper that records and replays commands against the db.
    """

    def __init__(self, db):
        self._db = db
        self._queue = []

    def sadd(self, key, *values):
        self._queue.append(["sadd", key, list(values)])
        return self

    def set(self, key, value):
        self._queue.append(["set", key, value])
        return self

    def smembers(self, key):
        self._queue.append(["smembers", key])
        return self

    def execute(self):
        results = []
        for item in self._queue:
            op = item[0]
            if op == "sadd":
                _, key, values = item
                self._db.setdefault(key, {"type": "set", "data": set()})
                for v in values:
                    self._db[key]["data"].add(v if isinstance(v, bytes) else v.encode())
                results.append(len(values))
            elif op == "set":
                _, key, value = item
                self._db[key] = {"type": "string", "data": value}
                results.append(True)
            elif op == "smembers":
                _, key = item
                entry = self._db.get(key, {"data": set()})
                results.append(set(entry["data"]))
        self._queue.clear()
        return results


class MockRedisServer:
    """
    Minimal in-memory Redis mock with the methods used by redis_cache.
    """

    def __init__(self):
        self.db = {}

    def pipeline(self):
        return MockRedisPipeline(self.db)

    def smembers(self, key):
        entry = self.db.get(key, {"data": set()})
        return set(entry["data"])

    def sadd(self, key, *values):
        self.db.setdefault(key, {"type": "set", "data": set()})
        for v in values:
            self.db[key]["data"].add(v if isinstance(v, bytes) else v.encode())
        return len(values)

    def get(self, key):
        entry = self.db.get(key)
        return entry["data"] if entry else None

    def set(self, key, value):
        self.db[key] = {"type": "string", "data": value}
        return True

    def sismember(self, key, value):
        entry = self.db.get(key, {"data": set()})
        v = value if isinstance(value, bytes) else value.encode()
        return v in entry["data"]

    def type(self, key):
        entry = self.db.get(key)
        return entry["type"] if entry else "none"


@pytest.fixture
def mock_redis(monkeypatch):
    """
    Monkeypatch the global REDIS_SERVER and __opts__ for isolated unit tests.
    """
    server = MockRedisServer()
    monkeypatch.setattr(redis_cache, "REDIS_SERVER", server, raising=False)
    monkeypatch.setattr(redis_cache, "__opts__", {}, raising=False)
    monkeypatch.setattr(redis_cache.time, "time", lambda: 0)
    return server


# ---------------------------------------------------------------------------
# Regression tests for PR #67814
# ---------------------------------------------------------------------------


def test_build_bank_hier_adds_child_name_not_dot(mock_redis):
    """
    Regression: _build_bank_hier() must add the child bank name (e.g. "myhost")
    to the parent bank SET, NOT the literal dot ".".

    Before the fix, every bank entry was b"." rather than the actual child name,
    so manage.up / manage.status returned empty minion lists.
    """
    redis_pipe = mock_redis.pipeline()
    redis_cache._build_bank_hier("minions/myhost", redis_pipe)
    redis_pipe.execute()

    # The "minions" bank SET must contain b"myhost", never b"."
    bank_key = redis_cache._get_bank_redis_key("minions")
    members = mock_redis.smembers(bank_key)
    assert (
        b"myhost" in members
    ), "child bank 'myhost' must be recorded in the minions bank hierarchy"
    assert b"." not in members, (
        "dot '.' must NOT appear in the bank hierarchy; "
        "it was a bug that caused empty minion lists"
    )


def test_list_returns_minion_ids_not_empty(mock_redis):
    """
    Regression: list_("minions") must return the stored minion IDs.

    Before the fix, list_() queried _get_bank_keys_redis_key("minions") which
    holds the *key names* under the "minions" bank (empty for a pure-hierarchy
    bank), so manage.* runners always got an empty list back.
    """
    redis_cache.store("minions/myhost", "data", {"id": "myhost"})
    redis_cache.store("minions/yourhost", "data", {"id": "yourhost"})

    result = redis_cache.list_("minions")

    assert "myhost" in result, "list_('minions') must include 'myhost'"
    assert "yourhost" in result, "list_('minions') must include 'yourhost'"
    assert "." not in result, "list_() must not return the sentinel dot '.'"


def test_list_returns_keys_when_no_sub_banks(mock_redis):
    """
    list_() on a leaf bank (one that holds keys, not sub-banks) must return
    the stored key names.
    """
    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})
    redis_cache.store("minions/myhost", "pillar", {"role": "web"})

    result = redis_cache.list_("minions/myhost")

    assert set(result) == {
        "grain",
        "pillar",
    }, "list_() on a leaf bank must return the key names stored in that bank"


def test_store_and_fetch_roundtrip(mock_redis):
    """
    Basic sanity: data stored under a bank/key must be retrievable via fetch().
    """
    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})
    result = redis_cache.fetch("minions/myhost", "grain")
    assert result == {"os": "Linux"}


def test_list_empty_bank(mock_redis):
    """
    list_() on a bank that has never been written to must return [].
    """
    result = redis_cache.list_("nonexistent/bank")
    assert result == []
