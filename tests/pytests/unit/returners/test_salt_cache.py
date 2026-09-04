"""
Unit tests for ``salt.returners.salt_cache`` — the job-cache returner
that routes through ``salt.cache.Cache``.

These tests pin the returner API contract (``prep_jid`` / ``returner``
/ ``save_load`` / ``save_minions`` / ``get_load`` / ``get_jid`` /
``get_jids`` / ``get_jids_filter`` / ``clean_old_jobs`` /
``update_endtime`` / ``get_endtime``) using the real ``localfs`` cache
driver so the on-disk behaviour is exercised end-to-end.

Multi-ring integration (``ring_membership.owns_for`` calls in
``salt.master``) is covered separately under
``tests/pytests/unit/test_event_monitor_ring_gating.py``; here we just
prove that this returner does what ``local_cache`` does, only via the
:class:`salt.cache.Cache` abstraction so the multi-ring runners can
operate on the data.
"""

import time

import pytest

import salt.cache
import salt.returners.salt_cache as salt_cache
from tests.support.mock import patch


@pytest.fixture
def opts(tmp_path):
    """
    Master opts pointing at a per-test cachedir with the default
    ``localfs`` cache driver.  Using a real driver (rather than a
    mock) catches wire-shape bugs that a tighter mock would mask.
    """
    return {
        "cachedir": str(tmp_path),
        "cache": "localfs",
        "extension_modules": str(tmp_path / "extmods"),
        "hash_type": "sha256",
        "keep_jobs_seconds": 86400,
        "job_cache_store_endtime": False,
    }


@pytest.fixture
def configure_loader_modules(opts):
    """Inject opts into the returner module the way Salt's loader would."""
    return {salt_cache: {"__opts__": opts}}


def _cache(opts):
    """Helper: independent Cache instance for inspecting writes."""
    return salt.cache.Cache(opts)


# ---------------------------------------------------------------------------
# prep_jid
# ---------------------------------------------------------------------------


def test_prep_jid_generates_jid_when_none_passed(opts):
    jid = salt_cache.prep_jid()
    assert isinstance(jid, str)
    assert len(jid) >= 8  # gen_jid always returns a non-trivial id


def test_prep_jid_honours_passed_jid(opts):
    jid = salt_cache.prep_jid(passed_jid="20260516-special")
    assert jid == "20260516-special"


def test_prep_jid_retries_on_collision(opts):
    """
    A generated jid that collides with an existing load triggers a
    fresh generate.  Pin via a controlled ``gen_jid`` that returns
    the same id twice then a new one — first round collides, second
    round wins.
    """
    cache = _cache(opts)
    cache.store("jobs/loads", "collide-1", {"fun": "test.ping"})

    sequence = iter(["collide-1", "collide-1", "fresh-2"])
    with patch("salt.utils.jid.gen_jid", lambda _opts: next(sequence)):
        jid = salt_cache.prep_jid()

    assert jid == "fresh-2"


def test_prep_jid_records_nocache_marker(opts):
    """
    ``nocache=True`` writes a marker so subsequent minion returns are
    dropped by :func:`returner`.
    """
    jid = salt_cache.prep_jid(nocache=True, passed_jid="20260516-nc")
    cache = _cache(opts)
    assert cache.contains("jobs/nocache", "20260516-nc")
    assert cache.fetch("jobs/nocache", jid) is True


# ---------------------------------------------------------------------------
# returner — minion returns
# ---------------------------------------------------------------------------


def test_returner_persists_minion_return(opts):
    salt_cache.returner(
        {
            "jid": "20260516-A",
            "id": "minion-a",
            "return": {"ok": True},
            "retcode": 0,
            "success": True,
        }
    )
    cache = _cache(opts)
    record = cache.fetch("jobs/returns/20260516-A", "minion-a")
    assert record == {"return": {"ok": True}, "retcode": 0, "success": True}


def test_returner_includes_out_when_present(opts):
    salt_cache.returner(
        {
            "jid": "20260516-B",
            "id": "minion-a",
            "return": "x",
            "out": "highstate",
        }
    )
    record = _cache(opts).fetch("jobs/returns/20260516-B", "minion-a")
    assert record["out"] == "highstate"


def test_returner_drops_duplicate_minion_returns(opts):
    """
    Replay protection: a second return from the same (jid, minion)
    is rejected without overwriting the first record.  Pins the
    invariant that returns are append-once.
    """
    load = {
        "jid": "20260516-C",
        "id": "minion-a",
        "return": "first",
        "retcode": 0,
        "success": True,
    }
    salt_cache.returner(load)

    second = dict(load, **{"return": "second"})
    assert salt_cache.returner(second) is False

    record = _cache(opts).fetch("jobs/returns/20260516-C", "minion-a")
    assert record["return"] == "first"


def test_returner_skips_when_nocache_marker_set(opts):
    salt_cache.prep_jid(nocache=True, passed_jid="20260516-nc-2")
    salt_cache.returner(
        {
            "jid": "20260516-nc-2",
            "id": "minion-a",
            "return": "x",
        }
    )
    # No return persisted for the nocache jid.
    assert _cache(opts).list("jobs/returns/20260516-nc-2") == []


# ---------------------------------------------------------------------------
# save_load + save_minions + get_load
# ---------------------------------------------------------------------------


def test_save_load_round_trips(opts):
    payload = {
        "fun": "test.ping",
        "arg": [],
        "tgt": "*",
        "tgt_type": "glob",
        "user": "ops",
    }
    # Pass an explicit minion list so save_load doesn't construct
    # CkMinions (which needs PKI-cache opts we don't carry in this
    # test harness).  The "compute matched set when tgt is set"
    # branch is exercised separately below by stubbing CkMinions.
    salt_cache.save_load("20260516-D", dict(payload), minions=["m1"])
    out = salt_cache.get_load("20260516-D")
    assert out["fun"] == "test.ping"
    assert out["tgt"] == "*"
    assert out["Minions"] == ["m1"]


def test_save_load_computes_matched_minions_when_not_supplied(opts):
    """
    With ``minions=None`` and a ``tgt`` in the load, ``save_load``
    invokes ``CkMinions`` to populate the matched set.  We stub it
    out so the test doesn't need a real PKI tree.
    """

    class _FakeCkMinions:
        def __init__(self, _opts):
            pass

        def check_minions(self, _tgt, _tgt_type="glob"):
            return {"minions": ["m1", "m2"]}

    with patch("salt.utils.minions.CkMinions", _FakeCkMinions):
        salt_cache.save_load(
            "20260516-D2",
            {"fun": "test.ping", "tgt": "*", "tgt_type": "glob"},
        )

    out = salt_cache.get_load("20260516-D2")
    assert out["Minions"] == ["m1", "m2"]


def test_save_load_skips_minion_computation_when_no_tgt(opts):
    """
    Loads without a ``tgt`` (e.g. runner jobs) must not invoke
    CkMinions — the matched set doesn't apply to them.
    """
    with patch.object(salt_cache, "save_minions") as save_minions_mock:
        salt_cache.save_load("20260516-E", {"fun": "test.ping"})
    save_minions_mock.assert_not_called()


def test_save_minions_merges_with_existing(opts):
    salt_cache.save_minions("20260516-F", ["minion-a", "minion-b"])
    # Second call merges; the master and the syndic each contribute
    # a slice of the same job's matched set.
    salt_cache.save_minions("20260516-F", ["minion-b", "minion-c"])
    assert _cache(opts).fetch("jobs/minions", "20260516-F") == [
        "minion-a",
        "minion-b",
        "minion-c",
    ]


def test_get_load_includes_sorted_minions(opts):
    salt_cache.save_load(
        "20260516-G",
        {"fun": "test.ping"},  # no tgt → no auto-save_minions
    )
    salt_cache.save_minions("20260516-G", ["m2", "m1", "m3"])

    load = salt_cache.get_load("20260516-G")
    assert load["Minions"] == ["m1", "m2", "m3"]


def test_get_load_returns_empty_dict_for_unknown_jid(opts):
    assert salt_cache.get_load("never-existed") == {}


# ---------------------------------------------------------------------------
# get_jid — all returns for one jid
# ---------------------------------------------------------------------------


def test_get_jid_returns_every_minion_record(opts):
    for minion in ("m1", "m2", "m3"):
        salt_cache.returner(
            {
                "jid": "20260516-H",
                "id": minion,
                "return": f"hello from {minion}",
                "retcode": 0,
                "success": True,
            }
        )
    got = salt_cache.get_jid("20260516-H")
    assert set(got) == {"m1", "m2", "m3"}
    assert got["m1"]["return"] == "hello from m1"


def test_get_jid_wraps_legacy_v1_payloads(opts):
    """
    Older returners stored the bare return value at the minion key
    instead of the ``{"return": …}`` dict.  ``get_jid`` must coerce
    those into the modern shape so callers see a consistent contract.
    """
    cache = _cache(opts)
    cache.store("jobs/returns/20260516-legacy", "m1", "bare-return-value")
    got = salt_cache.get_jid("20260516-legacy")
    assert got == {"m1": {"return": "bare-return-value"}}


# ---------------------------------------------------------------------------
# get_jids / get_jids_filter
# ---------------------------------------------------------------------------


def test_get_jids_returns_every_known_load(opts):
    for jid in ("20260516-J", "20260516-K"):
        salt_cache.save_load(jid, {"fun": "test.ping"})
    got = salt_cache.get_jids()
    assert set(got) == {"20260516-J", "20260516-K"}


def test_get_jids_filter_keeps_most_recent(opts):
    jids = ["20260516-0001", "20260516-0002", "20260516-0003"]
    for jid in jids:
        salt_cache.save_load(jid, {"fun": "test.ping"})

    out = salt_cache.get_jids_filter(count=2)
    assert len(out) == 2


def test_get_jids_filter_drops_find_job(opts):
    """``saltutil.find_job`` traffic is excluded by default."""
    salt_cache.save_load("20260516-Q", {"fun": "test.ping"})
    salt_cache.save_load("20260516-R", {"fun": "saltutil.find_job"})

    out = salt_cache.get_jids_filter(count=10)
    funs = [j.get("Function") for j in out]
    assert "saltutil.find_job" not in funs
    assert "test.ping" in funs


# ---------------------------------------------------------------------------
# Endtime
# ---------------------------------------------------------------------------


def test_endtime_round_trips(opts):
    salt_cache.update_endtime("20260516-T", 1234567890.0)
    assert salt_cache.get_endtime("20260516-T") == 1234567890.0


def test_get_endtime_returns_none_for_unknown_jid(opts):
    assert salt_cache.get_endtime("never-existed") is None


# ---------------------------------------------------------------------------
# clean_old_jobs
# ---------------------------------------------------------------------------


def test_clean_old_jobs_is_noop_when_retention_is_zero(opts):
    opts["keep_jobs_seconds"] = 0
    salt_cache.save_load("20260516-U", {"fun": "test.ping"})
    salt_cache.clean_old_jobs()
    # The load is still there.
    assert _cache(opts).contains("jobs/loads", "20260516-U")


def test_clean_old_jobs_drops_aged_entries(opts):
    """
    A load older than ``keep_jobs_seconds`` is removed along with
    every per-jid bank (returns, minions, endtimes, nocache).  We
    set retention to a tiny window and sleep just long enough to
    cross it.
    """
    opts["keep_jobs_seconds"] = 0.01

    # Seed: load, minions, an end-time, and one minion return.
    salt_cache.save_load("20260516-V", {"fun": "test.ping"})
    salt_cache.save_minions("20260516-V", ["m1"])
    salt_cache.update_endtime("20260516-V", 1.0)
    salt_cache.returner({"jid": "20260516-V", "id": "m1", "return": "ok"})

    cache = _cache(opts)
    assert cache.contains("jobs/loads", "20260516-V")

    # Cross the retention window.  localfs uses mtime which is
    # filesystem-bound; sleep a bit to ensure we're definitely past
    # the threshold.
    time.sleep(0.05)

    salt_cache.clean_old_jobs()

    assert not cache.contains("jobs/loads", "20260516-V")
    assert not cache.contains("jobs/minions", "20260516-V")
    assert not cache.contains("jobs/endtimes", "20260516-V")
    assert cache.list("jobs/returns/20260516-V") == []


def test_clean_old_jobs_keeps_fresh_entries(opts):
    """
    Loads younger than ``keep_jobs_seconds`` must survive the sweep
    — pins the invariant that ``clean_old_jobs`` is conservative.
    """
    opts["keep_jobs_seconds"] = 3600
    salt_cache.save_load("20260516-W", {"fun": "test.ping"})

    salt_cache.clean_old_jobs()

    assert _cache(opts).contains("jobs/loads", "20260516-W")
