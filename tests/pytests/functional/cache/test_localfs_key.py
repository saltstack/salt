import logging
import os
import time

import pytest

import salt.cache
from salt.exceptions import SaltCacheError
from salt.utils.files import fopen

log = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def cache(minion_opts):
    opts = minion_opts.copy()
    opts["cache"] = "localfs_key"
    cache = salt.cache.factory(opts)
    try:
        yield cache
    finally:
        for minion in ["minion_a", "minion_x", "minion_y", "minion_z", "minion_denied"]:
            cache.flush("keys", minion)
            cache.flush("denied_keys", minion)


# TODO: test user
def test_key_lifecycle(cache):
    pki_dir = cache.opts["pki_dir"]

    # key is put into pending
    cache.store("keys", "minion_a", {"state": "pending", "pub": "RSAKEY_minion_a"})

    assert os.path.exists(
        os.path.join(pki_dir, "minions_pre", "minion_a")
    ), "key was created"
    assert (
        fopen(os.path.join(pki_dir, "minions_pre", "minion_a"), "rb").read()
        == b"RSAKEY_minion_a"
    ), "key serialized to right content"

    assert cache.fetch("keys", "minion_a") == {
        "state": "pending",
        "pub": "RSAKEY_minion_a",
    }, "key fetched as expected"

    # key is moved to rejected from pending
    cache.store("keys", "minion_a", {"state": "rejected", "pub": "RSAKEY_minion_a"})

    assert not os.path.exists(
        os.path.join(pki_dir, "minions", "minion_a")
    ), "key was removed from created"
    assert os.path.exists(
        os.path.join(pki_dir, "minions_rejected", "minion_a")
    ), "key was added to rejected"
    assert (
        fopen(os.path.join(pki_dir, "minions_rejected", "minion_a"), "rb").read()
        == b"RSAKEY_minion_a"
    ), "key serialized as expected"

    assert cache.fetch("keys", "minion_a") == {
        "state": "rejected",
        "pub": "RSAKEY_minion_a",
    }, "key fetched as expected"

    # key is moved from rejected to accepted
    cache.store("keys", "minion_a", {"state": "accepted", "pub": "RSAKEY_minion_a"})

    assert not os.path.exists(
        os.path.join(pki_dir, "minions_rejected", "minion_a")
    ), "key was removed from rejected"
    assert os.path.exists(
        os.path.join(pki_dir, "minions", "minion_a")
    ), "key was added to minions"
    assert (
        fopen(os.path.join(pki_dir, "minions", "minion_a"), "rb").read()
        == b"RSAKEY_minion_a"
    ), "key serialized as expected"
    assert cache.fetch("keys", "minion_a") == {
        "state": "accepted",
        "pub": "RSAKEY_minion_a",
    }, "key fetched as expected"

    # key is moved to denied
    cache.store("denied_keys", "minion_a", ["RSAKEY_minion_b"])
    assert os.path.exists(
        os.path.join(pki_dir, "minions", "minion_a")
    ), "key remained in minions"
    assert os.path.exists(
        os.path.join(pki_dir, "minions_denied", "minion_a")
    ), "key remained in minions"
    assert (
        fopen(os.path.join(pki_dir, "minions_denied", "minion_a"), "rb").read()
        == b"RSAKEY_minion_b"
    ), "key serialized as expected"
    assert cache.fetch("denied_keys", "minion_a") == [
        "RSAKEY_minion_b"
    ], "key fetched as expected"


def test_updated(cache):
    now = time.time()

    cache.store("keys", "minion_a", {"state": "accepted", "pub": "RSAKEY_minion_a"})
    updated = cache.updated("keys", "minion_a")

    # add some buffer just incase
    assert updated - int(now) <= 1

    assert cache.updated("keys", "nonexistant") is None


def test_minion_id_validity(cache):
    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.store("keys", "foo/bar/..", {})

    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.fetch("keys", "foo/bar/..")

    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.updated("keys", "foo/bar/..")

    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.contains("keys", "foo/bar/..")

    with pytest.raises(SaltCacheError, match="not a valid minion_id"):
        cache.flush("keys", "foo/bar/..")


def test_fetch(cache):
    with pytest.raises(SaltCacheError, match="bug at call-site"):
        cache.fetch("keys", ".key_cache")

    with fopen(
        os.path.join(cache.opts["pki_dir"], "minions_rejected", "minion_x"), "w+b"
    ) as fh_:
        fh_.write(b"RSAKEY_minion_x")

    with fopen(
        os.path.join(cache.opts["pki_dir"], "minions_pre", "minion_y"), "w+b"
    ) as fh_:
        fh_.write(b"RSAKEY_minion_y")

    with fopen(
        os.path.join(cache.opts["pki_dir"], "minions", "minion_z"), "w+b"
    ) as fh_:
        fh_.write(b"RSAKEY_minion_z")

    # minions_denied does not get craeted automatically
    if not os.path.exists(os.path.join(cache.opts["pki_dir"], "minions_denied")):
        os.makedirs(os.path.join(cache.opts["pki_dir"], "minions_denied"))

    with fopen(
        os.path.join(cache.opts["pki_dir"], "minions_denied", "minion_denied"), "w+b"
    ) as fh_:
        fh_.write(b"RSAKEY_minion_denied")

    assert cache.fetch("keys", "minion_x") == {
        "state": "rejected",
        "pub": "RSAKEY_minion_x",
    }
    assert cache.fetch("keys", "minion_y") == {
        "state": "pending",
        "pub": "RSAKEY_minion_y",
    }
    assert cache.fetch("keys", "minion_z") == {
        "state": "accepted",
        "pub": "RSAKEY_minion_z",
    }
    assert cache.fetch("denied_keys", "minion_denied") == ["RSAKEY_minion_denied"]


def test_flush_contains(cache):
    # set up test state
    cache.store("keys", "minion_x", {"state": "pending", "pub": "RSAKEY_minion_x"})
    cache.store("keys", "minion_y", {"state": "accepted", "pub": "RSAKEY_minion_y"})
    cache.store("keys", "minion_z", {"state": "pending", "pub": "RSAKEY_minion_z"})
    cache.store("denied_keys", "minion_a", ["RSAKEY_minion_a"])

    # assert contains works as expected
    assert cache.contains("keys", "minion_x")
    assert cache.contains("keys", "minion_y")
    assert cache.contains("keys", "minion_z")
    assert cache.contains("denied_keys", "minion_a")

    # flush test state
    cache.flush("keys", "minion_x")
    cache.flush("keys", "minion_y")
    cache.flush("keys", "minion_z")
    cache.flush("denied_keys", "minion_a")

    # assert files on disk no longer exist mapping to the expected keys
    assert not os.path.exists(
        os.path.join(cache.opts["pki_dir"], "minions_pre", "minion_x")
    )
    assert not os.path.exists(
        os.path.join(cache.opts["pki_dir"], "minions_pre", "minion_y")
    )
    assert not os.path.exists(
        os.path.join(cache.opts["pki_dir"], "minions_", "minion_z")
    )
    assert not os.path.exists(
        os.path.join(cache.opts["pki_dir"], "minions_denied", "minion_a")
    )

    # assert contains no longer returns true
    assert not cache.contains("keys", "minion_x")
    assert not cache.contains("keys", "minion_y")
    assert not cache.contains("keys", "minion_z")
    assert not cache.contains("denied_keys", "minion_a")


def test_list(cache):
    # set up test state
    cache.store("keys", "minion_x", {"state": "pending", "pub": "RSAKEY_minion_x"})
    cache.store("keys", "minion_y", {"state": "accepted", "pub": "RSAKEY_minion_y"})
    cache.store("keys", "minion_z", {"state": "pending", "pub": "RSAKEY_minion_z"})
    cache.store("denied_keys", "minion_a", ["RSAKEY_minion_a"])

    # assert contains works as expected
    assert sorted(cache.list("keys")) == ["minion_x", "minion_y", "minion_z"]
    #
    # assert contains works as expected
    assert cache.list("denied_keys") == ["minion_a"]
