"""
Functional integration for the ``salt_cache`` returner.

The unit tests in ``tests/pytests/unit/returners/test_salt_cache.py``
exercise every returner function directly with ``__opts__`` injected
via the loader fixture.  This test goes one layer up: it loads the
returner the way Salt's master loader does it and calls into the
public ``salt.utils.job`` surface (``store_load``, ``store_job``,
``store_minions``), proving that flipping ``master_job_cache:
salt_cache`` actually routes every job-cache code path through the
:class:`salt.cache.Cache` abstraction.

Why this matters
----------------
The multi-ring gate sites in ``salt/master.py`` only intercept
``salt/job/*`` events when ``master_job_cache`` writes through
``salt.cache.Cache`` — otherwise ``cluster.shed_unowned`` /
``cluster.collect_from_peers`` can't see the data.  This test pins
that the wiring works end-to-end without needing a full cluster.
"""

import pytest

import salt.cache
import salt.loader
import salt.utils.job


@pytest.fixture
def master_opts(tmp_path):
    """
    Minimal master opts with the salt_cache returner selected.

    ``master_job_cache: salt_cache`` is the operator-facing knob; the
    rest are bookkeeping the loader needs (``extension_modules``,
    ``cachedir``, ``hash_type``).  Using the real ``localfs`` cache
    driver means writes hit disk in ``tmp_path`` — the test cleans
    up via pytest's tmp_path teardown.
    """
    import salt.config

    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = str(tmp_path)
    opts["extension_modules"] = str(tmp_path / "extmods")
    opts["master_job_cache"] = "salt_cache"
    opts["cache"] = "localfs"
    opts["keep_jobs_seconds"] = 86400
    return opts


@pytest.fixture
def mminion(master_opts):
    """
    A ``MasterMinion`` with the returners loaded.  ``salt.utils.job``
    builds one of these per call if not supplied; we pre-build it
    here so the test exercises a single returner load (faster + the
    same path the master daemon uses internally).
    """
    return salt.minion.MasterMinion(master_opts, states=False, rend=False)


def test_loader_resolves_salt_cache(master_opts, mminion):
    """
    The master loader resolves ``salt_cache`` and exposes every
    returner function the master and the cluster runners depend on.
    Pins the contract that ``master_job_cache: salt_cache`` is a
    valid drop-in for ``local_cache``.
    """
    for fname in (
        "salt_cache.prep_jid",
        "salt_cache.save_load",
        "salt_cache.save_minions",
        "salt_cache.returner",
        "salt_cache.get_load",
        "salt_cache.get_jid",
        "salt_cache.get_jids",
        "salt_cache.clean_old_jobs",
    ):
        assert fname in mminion.returners, f"missing returner function {fname}"


def test_save_load_routes_through_salt_cache(master_opts, mminion):
    """
    Calling ``salt_cache.save_load`` through the returner dispatch
    lands the pub load in ``jobs/loads`` — the bank
    ``cluster.shed_unowned`` reads to find shardable JIDs.  Pins
    the end-to-end wiring: the master daemon's publish path goes
    through this same dispatch (see
    :func:`salt.utils.job.store_job`'s ``saveload_fstr`` lookup at
    ``salt/utils/job.py``).
    """
    mminion.returners["salt_cache.save_load"](
        "20260516-A",
        {"jid": "20260516-A", "fun": "test.ping"},
    )
    cache = salt.cache.Cache(master_opts, driver="localfs")
    stored = cache.fetch("jobs/loads", "20260516-A")
    assert stored["fun"] == "test.ping"


def test_store_job_routes_through_salt_cache(master_opts, mminion):
    """
    A minion return lands in the per-JID returns bank.
    ``salt.utils.job.store_job`` is the master daemon's entry
    point; with ``master_job_cache: salt_cache`` it dispatches to
    ``salt_cache.returner``.
    ``cluster.shed_unowned``'s cascade flush
    (``jobs/returns/<jid>`` whole-bank drop) operates on exactly
    these entries.
    """
    # Master would normally save the load first via
    # ``salt_cache.save_load``; do the same here so the returner has
    # the JID registered.
    mminion.returners["salt_cache.save_load"](
        "20260516-B",
        {"jid": "20260516-B", "fun": "test.ping"},
    )
    salt.utils.job.store_job(
        master_opts,
        {
            "jid": "20260516-B",
            "id": "minion-a",
            "return": "pong",
            "retcode": 0,
            "success": True,
        },
        mminion=mminion,
    )
    cache = salt.cache.Cache(master_opts, driver="localfs")
    record = cache.fetch("jobs/returns/20260516-B", "minion-a")
    assert record["return"] == "pong"
    assert record["retcode"] == 0


def test_store_minions_routes_through_salt_cache(master_opts, mminion):
    """
    ``salt.utils.job.store_minions`` is what the cluster gate site
    in ``salt/master.py`` calls on a forwarded ``salt/job/<jid>/new``
    event.  Pin that the minion list lands in ``jobs/minions`` —
    the bank ``cluster.shed_unowned`` reads to know what's
    shardable.
    """
    salt.utils.job.store_minions(
        master_opts, "20260516-C", ["m1", "m2"], mminion=mminion
    )
    cache = salt.cache.Cache(master_opts, driver="localfs")
    assert cache.fetch("jobs/minions", "20260516-C") == ["m1", "m2"]


def test_get_load_round_trips_through_returner_dispatch(master_opts, mminion):
    """
    Read-back through the returner dispatch returns what was saved.
    Round-trips through the public ``salt.utils.job`` →
    ``salt_cache.get_load`` path so a UI/CLI consumer would see the
    same answer.
    """
    mminion.returners["salt_cache.save_load"](
        "20260516-D",
        {"jid": "20260516-D", "fun": "test.ping"},
    )
    out = mminion.returners["salt_cache.get_load"]("20260516-D")
    assert out["fun"] == "test.ping"


# Lazy import: ``salt.minion`` pulls in a lot; only imported when a
# test actually requests the ``mminion`` fixture.  Avoids the cost
# on test collection for sibling functional tests that don't need it.
import salt.minion  # noqa: E402  pylint: disable=wrong-import-position
