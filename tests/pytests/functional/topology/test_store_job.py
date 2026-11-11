"""
Functional tests for ``cluster_path`` support in
:func:`salt.utils.job.store_job`.

Scope (master-topology RFC, section "Modifications to existing files"
> ``salt/utils/job.py``):

* Legacy call shape ``store_job(opts, load)`` is unaffected.
* ``cluster_path=("east",)`` disambiguates returns in the local_cache
  returner so duplicate minion-ids from different topology clusters
  do not clobber one another.
* ``cluster_path=None`` is identical to legacy behavior.
* Event-bus firing: when ``cluster_path`` is set, the fired event
  payload carries a ``cluster_path`` field.

Uses the real ``local_cache`` returner (no mocks) so that the test
exercises the shim's effect on the on-disk layout, which is the
observable contract for returners that key by a flat path.
"""

import pathlib

import salt.utils.event
import salt.utils.jid
import salt.utils.job

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_opts(minion_opts):
    opts = minion_opts.copy()
    opts["master_job_cache"] = "local_cache"
    opts["job_cache"] = True
    opts["ext_job_cache"] = ""
    return opts


def _make_load(minion_id, jid):
    return {
        "id": minion_id,
        "tgt": minion_id,
        "jid": jid,
        "return": {
            "fun": "test.ping",
            "jid": jid,
            "fun_args": [],
            "return": True,
            "success": True,
        },
    }


def _jid_dir(opts, jid):
    """
    Return the on-disk jid directory used by the ``local_cache``
    returner for the given opts + jid.  Mirrors the computation in
    :func:`salt.returners.local_cache._job_dir`.
    """
    import salt.utils.jid as jid_utils

    jobs_root = pathlib.Path(opts["cachedir"], "jobs")
    return pathlib.Path(jid_utils.jid_dir(jid, str(jobs_root), opts["hash_type"]))


class _CapturingEvent:
    """Minimal event-bus stand-in that records fired events."""

    def __init__(self):
        self.events = []
        self.ret_loads = []

    def fire_event(self, load, tag):
        self.events.append((tag, load))

    def fire_ret_load(self, load):
        self.ret_loads.append(load)


# ---------------------------------------------------------------------------
# Legacy / backward-compat shape
# ---------------------------------------------------------------------------


def test_legacy_call_shape_still_works(minion_opts, tmp_path):
    """
    ``store_job(opts, load)`` with only the two legacy positional
    arguments must continue to work: it writes the return into the
    minion-id subdirectory under the jid dir.
    """
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)
    load = _make_load("web-01", jid)

    salt.utils.job.store_job(opts, load)

    jid_dir = _jid_dir(opts, jid)
    assert (jid_dir / "web-01" / "return.p").is_file()
    assert (jid_dir / ".load.p").is_file()


def test_legacy_four_positional_shape_still_works(minion_opts):
    """
    Existing callers that pass ``(opts, load, event, mminion)`` --- the
    shape used by :class:`salt.client.mixins.SyncClientMixin` --- must
    keep working after the ``cluster_path`` parameter is added.
    """
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)
    load = _make_load("web-01", jid)
    event = _CapturingEvent()

    # Positional event + mminion=None (the common call shape).
    salt.utils.job.store_job(opts, load, event, None)

    jid_dir = _jid_dir(opts, jid)
    assert (jid_dir / "web-01" / "return.p").is_file()
    # And the event fired as before, with no cluster_path field.
    assert event.events, "expected a job-return event to be fired"
    _tag, fired_load = event.events[0]
    assert "cluster_path" not in fired_load


def test_cluster_path_none_matches_legacy(minion_opts):
    """``cluster_path=None`` is a no-op --- identical to legacy."""
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)
    load = _make_load("web-01", jid)

    salt.utils.job.store_job(opts, load, cluster_path=None)

    jid_dir = _jid_dir(opts, jid)
    assert (jid_dir / "web-01" / "return.p").is_file()


def test_empty_cluster_path_matches_legacy(minion_opts):
    """An empty tuple is treated the same as ``None``."""
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)
    load = _make_load("web-01", jid)

    salt.utils.job.store_job(opts, load, cluster_path=())

    jid_dir = _jid_dir(opts, jid)
    assert (jid_dir / "web-01" / "return.p").is_file()


# ---------------------------------------------------------------------------
# cluster_path extends the on-disk key
# ---------------------------------------------------------------------------


def test_cluster_path_single_segment_prefixes_id(minion_opts):
    """
    ``cluster_path=("east",)`` must land the per-minion directory at
    ``<jid>/east/web-01/return.p`` --- the "flat-path returner" shim
    joins the cluster_path with ``/`` and uses it as a prefix on the
    minion id.
    """
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)
    load = _make_load("web-01", jid)

    salt.utils.job.store_job(opts, load, cluster_path=("east",))

    jid_dir = _jid_dir(opts, jid)
    assert (jid_dir / "east" / "web-01" / "return.p").is_file()
    # Must NOT have created the unqualified minion dir.
    assert not (jid_dir / "web-01" / "return.p").is_file()


def test_duplicate_minion_id_across_clusters_no_clobber(minion_opts):
    """
    Same jid + same minion-id from different ``cluster_path`` must
    not clobber one another --- both on-disk entries exist.
    """
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)

    east_load = _make_load("web-01", jid)
    east_load["return"]["return"] = "east-payload"
    west_load = _make_load("web-01", jid)
    west_load["return"]["return"] = "west-payload"

    salt.utils.job.store_job(opts, east_load, cluster_path=("east",))
    salt.utils.job.store_job(opts, west_load, cluster_path=("west",))

    jid_dir = _jid_dir(opts, jid)
    east_ret = jid_dir / "east" / "web-01" / "return.p"
    west_ret = jid_dir / "west" / "web-01" / "return.p"
    assert east_ret.is_file()
    assert west_ret.is_file()
    assert east_ret.read_bytes() != west_ret.read_bytes()


# ---------------------------------------------------------------------------
# Event-bus payload carries cluster_path when present
# ---------------------------------------------------------------------------


def test_event_payload_includes_cluster_path(minion_opts):
    """
    When ``cluster_path`` is set, the fired job-return event payload
    carries a ``cluster_path`` field.  Legacy callers (no
    cluster_path) see no such field (covered by
    :func:`test_legacy_four_positional_shape_still_works`).
    """
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)
    load = _make_load("web-01", jid)
    event = _CapturingEvent()

    salt.utils.job.store_job(opts, load, event=event, cluster_path=("east",))

    assert event.events, "expected a job-return event to be fired"
    _tag, fired_load = event.events[0]
    assert fired_load.get("cluster_path") == ["east"] or fired_load.get(
        "cluster_path"
    ) == ("east",)
    # fire_ret_load also receives the annotated load.
    assert event.ret_loads
    assert event.ret_loads[0].get("cluster_path") in (["east"], ("east",))


def test_event_payload_cluster_path_nested(minion_opts):
    """Nested cluster_path flows through to the event payload."""
    opts = _make_opts(minion_opts)
    jid = salt.utils.jid.gen_jid(opts)
    load = _make_load("web-01", jid)
    event = _CapturingEvent()

    salt.utils.job.store_job(opts, load, event=event, cluster_path=("east", "sub1"))

    assert event.events
    _tag, fired_load = event.events[0]
    cp = fired_load.get("cluster_path")
    assert cp in (["east", "sub1"], ("east", "sub1"))
