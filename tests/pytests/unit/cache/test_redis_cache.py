"""
unit tests for the redis_cache cache
"""

import logging

import pytest

import salt.cache.redis_cache as redis_cache

log = logging.getLogger(__name__)


class MockRedisCache():
    """
    Mock a redis server.

    This implements the functions used for the redis cache. It would be great to test with a real
    server as differences between how the real interface works and the mocked one could cause test
    failures.
    """

    def __init__(self):
        self.results = []
        self.db = {}

    def pipeline(self):
        return self

    def execute(self):
        tmp = self.results
        self.results = []
        return tmp

    def _get_type(self, key, typename, default):
        redis_val = self.db.get(key)
        if not redis_val:
            redis_val = {"type": typename, "data": default}
        if redis_val["type"] != typename:
            raise TypeError("{0} is not {1}".format(key, typename))
        return redis_val

    def unlink(self, *keys):
        for key in keys:
            self._unlink(key)

    def _unlink(self, key):
        self.db.pop(key, None)
        self.results.append(None)

    def zadd(self, key, items):
        keyset = self._get_type(key, "sortedset", {})
        items = {k if isinstance(k, bytes) else k.encode("utf8"): s for k, s in items.items()}
        keyset["data"].update(items)
        self.db[key] = keyset
        self.results.append(None)

    def zrem(self, key, *fields):
        for field in fields:
            self._zrem(key, field)

    def _zrem(self, key, field):
        keyset = self._get_type(key, "sortedset", {})
        if not isinstance(field, bytes):
            field = field.encode("utf8")
        keyset["data"].pop(field, None)
        if len(keyset["data"]) == 0:
            self.db.pop(key, None)
        self.results.append(None)

    def zrange(self, key, start, stop, bylex=False):
        include_start = start[0] == "["
        include_stop = stop[0] == "["
        keyset = self._get_type(key, "sortedset", {})
        listing = []
        if bylex:
            start = start[1:].encode("utf8")
            stop = stop[1:].encode("utf8")
            for field, score in keyset["data"].items():
                if include_start and field == start:
                    listing.append(field)
                elif start < field and field < stop:
                    listing.append(field)
                elif include_stop and field == stop:
                    listing.append(field)
        else:
            start = int(start[1:])
            stop = int(stop[1:])
            for field, score in keyset["data"].items():
                if include_start and score == int(start):
                    listing.append(field)
                elif int(start) < score and score < int(stop):
                    listing.append(field)
                elif include_stop and score == int(stop):
                    listing.append(field)
        self.results.append(listing)
        return self.results[-1]

    def hset(self, key, field, value):
        hashmap = self._get_type(key, "hash", {})
        if not isinstance(field, bytes):
            field = field.encode("utf8")
        if not isinstance(value, bytes):
            value = value.encode("utf8")
        hashmap["data"][field] = value
        self.db[key] = hashmap
        self.results.append(None)

    def hget(self, key, field):
        hashmap = self._get_type(key, "hash", {})
        if not isinstance(field, bytes):
            field = field.encode("utf8")
        self.results.append(hashmap["data"].get(field))
        return self.results[-1]

    def hkeys(self, key):
        hashmap = self._get_type(key, "hash", {})
        self.results.append(list(hashmap["data"].keys()))
        return self.results[-1]

    def hexists(self, key, field):
        hashmap = self._get_type(key, "hash", {})
        if not isinstance(field, bytes):
            field = field.encode("utf8")
        self.results.append(field in hashmap["data"])
        return self.results[-1]

    def hdel(self, key, field):
        hashmap = self._get_type(key, "hash", {})
        if not isinstance(field, bytes):
            field = field.encode("utf8")
        hashmap["data"].pop(field, None)
        if len(hashmap["data"]) == 0:
            self.db.pop(key, None)
        self.results.append(None)

    def exists(self, key):
        self.results.append(key in self.db)
        return self.results[-1]


@pytest.fixture
def mock_redis_cache(monkeypatch):
    monkeypatch.setattr(redis_cache, "__opts__", {}, raising=False)
    monkeypatch.setattr(redis_cache, "__context__", {
        "cache.redis": {
            "client": MockRedisCache(),
            "banks_prefix": redis_cache._BANKS_PREFIX + "_",
            "keys_prefix": redis_cache._KEYS_PREFIX + "_",
            "timestamp_prefix": redis_cache._TIMESTAMP_PREFIX + "_",
        }
    }, raising=False)
    monkeypatch.setattr(redis_cache.time, "time", lambda: 0)


def test_basic_store(mock_redis_cache):
    """
    Test that a basic store creates the expected database.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})

    expected = {
        "$BANKS_": {"type": "sortedset", "data": {b"$KEYS_minions/myhost/": 0}},
        "$KEYS_minions/myhost/": {"type": "hash", "data": {b"grain": b"\x81\xa2os\xa5Linux"}},
        "$TSTAMP_minions/myhost/": {"type": "hash", "data": {b"grain": b"\x00"}},
    }
    assert expected == redis_server.db


def test_store_multiple(mock_redis_cache):
    """
    Store multiple entries in the cache.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})
    redis_cache.store("minions/myhost", "pillar", {"os": "Linux"})
    redis_cache.store("minions/myhost/vm", "grain", {"os": "Windows"})
    redis_cache.store("minions/myhost/vm", "pillar", {"os": "Windows"})
    redis_cache.store("minions/yourhost", "grain", {"os": "MacOS"})
    redis_cache.store("minions/yourhost", "pillar", {"os": "MacOS"})

    expected = {
        "$BANKS_": {"type": "sortedset", "data": {b"$KEYS_minions/myhost/": 0, b"$KEYS_minions/myhost/vm/": 0, b"$KEYS_minions/yourhost/": 0}},
        "$KEYS_minions/myhost/": {"type": "hash", "data": {b"grain": b"\x81\xa2os\xa5Linux", b"pillar": b"\x81\xa2os\xa5Linux"}},
        "$TSTAMP_minions/myhost/": {"type": "hash", "data": {b"grain": b"\x00", b"pillar": b"\x00"}},
        "$KEYS_minions/myhost/vm/": {"type": "hash", "data": {b"grain": b"\x81\xa2os\xa7Windows", b"pillar": b"\x81\xa2os\xa7Windows"}},
        "$TSTAMP_minions/myhost/vm/": {"type": "hash", "data": {b"grain": b"\x00", b"pillar": b"\x00"}},
        "$KEYS_minions/yourhost/": {"type": "hash", "data": {b"grain": b"\x81\xa2os\xa5MacOS", b"pillar": b"\x81\xa2os\xa5MacOS"}},
        "$TSTAMP_minions/yourhost/": {"type": "hash", "data": {b"grain": b"\x00", b"pillar": b"\x00"}},
    }
    assert expected == redis_server.db


def test_basic_fetch(mock_redis_cache):
    """
    Test that a basic fetch retrieves the correct value.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})

    assert {"os": "Linux"} == redis_cache.fetch("minions/myhost", "grain")


def test_basic_updated(mock_redis_cache):
    """
    Test that updated retrieves the correct value.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})

    assert redis_cache.updated("minions/myhost", "grain") == 0


def test_remove_single(mock_redis_cache):
    """
    Remove the last entry in the cache.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})
    redis_cache.flush("minions/myhost", "grain")

    expected = {}
    assert expected == redis_server.db


def test_remove_remaining(mock_redis_cache):
    """
    Remove only some of the data.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})
    redis_cache.store("minions/myhost", "pillar", {"os": "Linux"})
    redis_cache.flush("minions/myhost", "pillar")

    expected = {
        "$BANKS_": {"type": "sortedset", "data": {b"$KEYS_minions/myhost/": 0}},
        "$KEYS_minions/myhost/": {"type": "hash", "data": {b"grain": b"\x81\xa2os\xa5Linux"}},
        "$TSTAMP_minions/myhost/": {"type": "hash", "data": {b"grain": b"\x00"}},
    }
    assert expected == redis_server.db


def test_flush_bank(mock_redis_cache):
    """
    Remove an entire bank.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})
    redis_cache.store("minions/myhost", "pillar", {"os": "Linux"})
    redis_cache.store("minions/myhost/vm", "grain", {"os": "Windows"})
    redis_cache.store("minions/myhost/vm", "pillar", {"os": "Windows"})
    redis_cache.store("minions/yourhost", "grain", {"os": "MacOS"})
    redis_cache.store("minions/yourhost", "pillar", {"os": "MacOS"})

    redis_cache.flush("minions/myhost")
    expected = {
        "$BANKS_": {"type": "sortedset", "data": {b"$KEYS_minions/yourhost/": 0}},
        "$KEYS_minions/yourhost/": {"type": "hash", "data": {b"grain": b"\x81\xa2os\xa5MacOS", b"pillar": b"\x81\xa2os\xa5MacOS"}},
        "$TSTAMP_minions/yourhost/": {"type": "hash", "data": {b"grain": b"\x00", b"pillar": b"\x00"}},
    }
    assert expected == redis_server.db


def test_contains(mock_redis_cache):
    """
    Check the contains works.
    """

    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})

    assert redis_cache.contains("minions/myhost") is True
    assert redis_cache.contains("minions/myhost", "grain") is True
    assert redis_cache.contains("minions/yourhost") is False
    assert redis_cache.contains("minions/yourhost", "grain") is False


def test_list_simple(mock_redis_cache):
    """
    Test that the list works correctly.
    """
    redis_server = redis_cache.__context__["cache.redis"]["client"]

    redis_cache.store("minions/myhost", "grain", {"os": "Linux"})
    redis_cache.store("minions/myhost/vm", "gain", {"os": "Windows"})
    redis_cache.store("minions/yourhost", "grain", {"os": "MacOS"})

    assert {"vm", "grain"} == set(redis_cache.list_("minions/myhost"))
    assert {"myhost", "yourhost"} == set(redis_cache.list_("minions"))
