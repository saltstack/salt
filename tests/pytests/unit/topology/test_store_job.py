"""
Unit tests for the ``cluster_path`` flat-path shim in
:func:`salt.utils.job.store_job`.

Covers the pure-logic shim without touching
:class:`~salt.minion.MasterMinion`: a stub ``mminion`` captures the
``load`` passed to the returner so we can assert the shim mutates
``load["id"]`` into ``"/".join([*cluster_path, id])`` exactly as the
RFC specifies.

Scope (manager prompt):

* ``cluster_path=("east",)`` + ``id="web-01"`` --> returner sees
  ``"east/web-01"``.
* Nested ``cluster_path=("east", "sub1")`` --> ``"east/sub1/web-01"``.
* Empty ``cluster_path=()`` is equivalent to ``cluster_path=None``:
  the returner sees the native id, unmodified.
"""

import salt.utils.job


class _StubReturner:
    """Captures the ``load`` passed by ``_store_job`` to each returner function."""

    def __init__(self):
        self.returner_calls = []
        self.save_load_calls = []
        self.get_load_result = None  # dedup check path --> save_load gets called

    def returner(self, load):
        # local_cache uses ``load["id"]`` as the per-minion dir.
        self.returner_calls.append(dict(load))

    def save_load(self, jid, load):
        self.save_load_calls.append((jid, dict(load)))

    def get_load(self, jid):
        return self.get_load_result

    def prep_jid(self, *args, **kwargs):
        # Not exercised in these flows (jid is a real jid, not "req"),
        # but keep a stub so lookups don't raise KeyError if hit.
        return args[0] if args else kwargs.get("passed_jid")


class _StubMMinion:
    """Minimal mminion.returners[func] dispatch surface."""

    def __init__(self, job_cache):
        self._stub = _StubReturner()
        self.returners = {
            f"{job_cache}.returner": self._stub.returner,
            f"{job_cache}.save_load": self._stub.save_load,
            f"{job_cache}.get_load": self._stub.get_load,
            f"{job_cache}.prep_jid": self._stub.prep_jid,
        }

    @property
    def captured(self):
        return self._stub


def _opts():
    return {
        "master_job_cache": "stubcache",
        "job_cache": True,
        "ext_job_cache": "",
        "hash_type": "sha256",
        "cachedir": "/tmp/unused-cachedir-for-unit-test",
        # valid_id is bypassed because we call ``_store_job`` directly.
    }


def _load(minion_id, jid):
    return {
        "id": minion_id,
        "jid": jid,
        "return": {"fun": "test.ping", "return": True, "success": True},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_flat_path_shim_single_segment():
    """
    ``cluster_path=("east",)`` + ``id="web-01"`` --> the flat-path
    returner receives ``load["id"] == "east/web-01"``.
    """
    opts = _opts()
    mminion = _StubMMinion(opts["master_job_cache"])
    jid = "20260101000000000001"
    load = _load("web-01", jid)

    # Bypass valid_id by calling the private helper directly.
    salt.utils.job._store_job(
        opts, load, event=None, mminion=mminion, cluster_path=("east",)
    )

    assert mminion.captured.returner_calls, "returner was never called"
    seen = mminion.captured.returner_calls[0]
    assert seen["id"] == "east/web-01"
    # The caller's ``load`` must be restored (swap-and-restore).
    assert load["id"] == "web-01"
    # Annotation is on the caller's load too.
    assert load.get("cluster_path") == ["east"]


def test_flat_path_shim_nested_segments():
    """``cluster_path=("east", "sub1")`` --> ``"east/sub1/web-01"``."""
    opts = _opts()
    mminion = _StubMMinion(opts["master_job_cache"])
    jid = "20260101000000000002"
    load = _load("web-01", jid)

    salt.utils.job._store_job(
        opts,
        load,
        event=None,
        mminion=mminion,
        cluster_path=("east", "sub1"),
    )

    seen = mminion.captured.returner_calls[0]
    assert seen["id"] == "east/sub1/web-01"
    assert load["id"] == "web-01"
    assert load.get("cluster_path") == ["east", "sub1"]


def test_empty_cluster_path_tuple_equivalent_to_none():
    """
    ``cluster_path=()`` must be equivalent to ``cluster_path=None``:
    the returner sees the native id and no ``cluster_path`` field is
    added to the load.
    """
    opts = _opts()
    mminion_none = _StubMMinion(opts["master_job_cache"])
    mminion_empty = _StubMMinion(opts["master_job_cache"])
    jid = "20260101000000000003"

    load_none = _load("web-01", jid)
    load_empty = _load("web-01", jid)

    # The public ``store_job`` is where the empty-tuple normalization
    # happens.  Rather than wire ``valid_id`` + MasterMinion for this
    # unit test, exercise the normalization indirectly: call
    # ``_store_job`` with cluster_path=None and with cluster_path=()
    # and assert both arrive at the same returner-observed load.
    # (The public-wrapper normalization is covered functionally by
    # ``test_empty_cluster_path_matches_legacy``.)
    salt.utils.job._store_job(
        opts, load_none, event=None, mminion=mminion_none, cluster_path=None
    )
    salt.utils.job._store_job(
        opts, load_empty, event=None, mminion=mminion_empty, cluster_path=()
    )

    seen_none = mminion_none.captured.returner_calls[0]
    seen_empty = mminion_empty.captured.returner_calls[0]
    assert seen_none["id"] == "web-01"
    assert seen_empty["id"] == "web-01"
    assert "cluster_path" not in seen_none
    assert "cluster_path" not in seen_empty
    assert "cluster_path" not in load_none
    assert "cluster_path" not in load_empty
