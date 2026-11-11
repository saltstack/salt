"""
Functional tests for ``local_cache`` cluster_path support (RFC item 9).

The ``local_cache`` returner persists an optional ``cluster_path.p``
sidecar when a return load carries a ``cluster_path`` key.  This
disambiguates duplicate minion ids coming back from different clusters
in a topology deployment while remaining byte-identical on-disk for
pre-topology installs.
"""

import os

import pytest

import salt.payload
import salt.returners.local_cache as local_cache
import salt.utils.files
import salt.utils.jid


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """A clean per-test jobs cache directory wired into __opts__."""
    cache = tmp_path / "cache"
    (cache / "jobs").mkdir(parents=True)
    opts = {"cachedir": str(cache), "hash_type": "sha256"}
    monkeypatch.setattr(local_cache, "__opts__", opts, raising=False)
    return cache


def _prep_jid_dir(cache_dir, jid):
    jid_dir = salt.utils.jid.jid_dir(
        jid, os.path.join(str(cache_dir), "jobs"), "sha256"
    )
    os.makedirs(jid_dir, exist_ok=True)
    return jid_dir


def test_returner_without_cluster_path_writes_no_sidecar(cache_dir):
    """
    Pre-topology load (no ``cluster_path`` key) must not create the
    ``cluster_path.p`` sidecar — the on-disk shape stays byte-identical
    to a pre-RFC install.
    """
    jid = "20260101000000000001"
    _prep_jid_dir(cache_dir, jid)
    local_cache.returner(
        {
            "jid": jid,
            "id": "minion-a",
            "fun": "test.ping",
            "return": True,
            "success": True,
            "retcode": 0,
        }
    )
    hn_dir = os.path.join(
        salt.utils.jid.jid_dir(jid, os.path.join(str(cache_dir), "jobs"), "sha256"),
        "minion-a",
    )
    assert os.path.isfile(os.path.join(hn_dir, local_cache.RETURN_P))
    assert not os.path.exists(os.path.join(hn_dir, local_cache.CLUSTER_PATH_P))


def test_returner_with_cluster_path_writes_sidecar(cache_dir):
    """A load carrying ``cluster_path`` persists the annotation."""
    jid = "20260101000000000002"
    _prep_jid_dir(cache_dir, jid)
    local_cache.returner(
        {
            "jid": jid,
            "id": "minion-a",
            "fun": "test.ping",
            "return": True,
            "success": True,
            "retcode": 0,
            "cluster_path": ["east", "central"],
        }
    )
    hn_dir = os.path.join(
        salt.utils.jid.jid_dir(jid, os.path.join(str(cache_dir), "jobs"), "sha256"),
        "minion-a",
    )
    cp_path = os.path.join(hn_dir, local_cache.CLUSTER_PATH_P)
    assert os.path.isfile(cp_path)
    with salt.utils.files.fopen(cp_path, "rb") as fh:
        decoded = salt.payload.load(fh)
    assert decoded == ["east", "central"]


def test_get_jid_includes_cluster_path(cache_dir):
    """``get_jid`` surfaces the sidecar on the returned record."""
    jid = "20260101000000000003"
    _prep_jid_dir(cache_dir, jid)
    local_cache.returner(
        {
            "jid": jid,
            "id": "minion-a",
            "fun": "test.ping",
            "return": "ok",
            "success": True,
            "retcode": 0,
            "cluster_path": ["east"],
        }
    )
    got = local_cache.get_jid(jid)
    assert "minion-a" in got
    assert got["minion-a"]["cluster_path"] == ["east"]
    assert got["minion-a"]["return"] == "ok"


def test_get_jid_backward_compat_without_sidecar(cache_dir):
    """
    An existing (pre-topology) return directory lacking the sidecar is
    read as it always was — no ``cluster_path`` key, no error.
    """
    jid = "20260101000000000004"
    _prep_jid_dir(cache_dir, jid)
    local_cache.returner(
        {
            "jid": jid,
            "id": "minion-a",
            "fun": "test.ping",
            "return": "ok",
            "success": True,
            "retcode": 0,
        }
    )
    got = local_cache.get_jid(jid)
    assert "cluster_path" not in got["minion-a"]
    assert got["minion-a"]["return"] == "ok"


def test_get_jid_corrupt_sidecar_falls_through(cache_dir):
    """
    If the sidecar is corrupt (truncated/garbage), the primary return
    is still surfaced — the cluster_path annotation is silently
    skipped rather than crashing lookup.
    """
    jid = "20260101000000000005"
    _prep_jid_dir(cache_dir, jid)
    local_cache.returner(
        {
            "jid": jid,
            "id": "minion-a",
            "fun": "test.ping",
            "return": "ok",
            "success": True,
            "retcode": 0,
            "cluster_path": ["east"],
        }
    )
    hn_dir = os.path.join(
        salt.utils.jid.jid_dir(jid, os.path.join(str(cache_dir), "jobs"), "sha256"),
        "minion-a",
    )
    with salt.utils.files.fopen(
        os.path.join(hn_dir, local_cache.CLUSTER_PATH_P), "wb"
    ) as fh:
        fh.write(b"\x00\x00garbage not msgpack")
    got = local_cache.get_jid(jid)
    # Primary return still accessible; cluster_path either absent or
    # whatever the corrupt payload happened to decode as (but no exc).
    assert got["minion-a"]["return"] == "ok"


def test_multiple_minions_distinct_cluster_paths(cache_dir):
    """
    Two returns from different clusters at the same jid stay
    distinguishable via their cluster_path annotations.
    """
    jid = "20260101000000000006"
    _prep_jid_dir(cache_dir, jid)
    for mid, path in (("web-01", ["east"]), ("web-02", ["west"])):
        local_cache.returner(
            {
                "jid": jid,
                "id": mid,
                "fun": "test.ping",
                "return": "ok",
                "success": True,
                "retcode": 0,
                "cluster_path": path,
            }
        )
    got = local_cache.get_jid(jid)
    assert got["web-01"]["cluster_path"] == ["east"]
    assert got["web-02"]["cluster_path"] == ["west"]
