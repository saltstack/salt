"""
Unit tests for the multi_returner returner.

Regression tests for the fixes in PR #67880:

* ``save_load`` must skip ``local_cache`` when ``clear_load['cmd'] == '_return'``
  to mirror the dedup performed by ``salt.utils.job.store_job`` and stop the
  minion's ``_return`` payload from overwriting the dispatch-time load that
  the master already saved.
* ``save_load`` must forward ``minions`` to each configured sub-returner;
  previously the argument was dropped on the way through.
* ``get_jids_filter`` must dispatch under the canonical plural name (the
  runner in ``salt/runners/jobs.py`` looks up ``<returner>.get_jids_filter``)
  and merge results from every configured returner that implements it.
* ``save_reg`` must write to *every* configured returner that implements it,
  preserving the multi_returner write-to-all contract.
"""

import pytest

import salt.returners.multi_returner as multi_returner
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        multi_returner: {
            "__opts__": {multi_returner.CONFIG_KEY: ["local_cache", "fake_returner"]}
        }
    }


@pytest.fixture(autouse=True)
def _reset_mminion_cache():
    """Each test gets a fresh module-level MMINION."""
    with patch.object(multi_returner, "MMINION", None):
        yield


def _fake_mminion(returners):
    """Build a fake mminion whose .returners dict behaves like Salt's loader."""
    fake = MagicMock()
    fake.returners = returners
    return fake


def test_save_load_skips_local_cache_for_return_cmd():
    """
    PR #67880: when the load is the minion's ``_return`` payload, the
    dispatch-time load that the master already wrote to local_cache must
    not be overwritten.
    """
    local_cache_save_load = MagicMock()
    fake_save_load = MagicMock()
    fake = _fake_mminion(
        {
            "local_cache.save_load": local_cache_save_load,
            "fake_returner.save_load": fake_save_load,
        }
    )
    with patch.object(multi_returner, "_mminion", return_value=fake):
        multi_returner.save_load(
            "20260608000000000001",
            {"cmd": "_return", "jid": "20260608000000000001", "return": "result"},
        )

    local_cache_save_load.assert_not_called()
    fake_save_load.assert_called_once()


def test_save_load_dispatches_for_non_return_cmd():
    """
    Non-``_return`` loads (publish, runner, etc.) must still reach every
    configured returner, including local_cache.
    """
    local_cache_save_load = MagicMock()
    fake_save_load = MagicMock()
    fake = _fake_mminion(
        {
            "local_cache.save_load": local_cache_save_load,
            "fake_returner.save_load": fake_save_load,
        }
    )
    with patch.object(multi_returner, "_mminion", return_value=fake):
        multi_returner.save_load(
            "20260608000000000002",
            {"cmd": "publish", "jid": "20260608000000000002", "tgt": "*"},
            minions=["minion-1", "minion-2"],
        )

    local_cache_save_load.assert_called_once_with(
        "20260608000000000002",
        {"cmd": "publish", "jid": "20260608000000000002", "tgt": "*"},
        ["minion-1", "minion-2"],
    )
    fake_save_load.assert_called_once_with(
        "20260608000000000002",
        {"cmd": "publish", "jid": "20260608000000000002", "tgt": "*"},
        ["minion-1", "minion-2"],
    )


def test_save_load_forwards_minions_argument():
    """
    Prior to PR #67880, ``save_load`` dropped its ``minions`` kwarg before
    dispatching — every sub-returner saw ``minions=None`` regardless of
    what the master passed. This regression-pins the forwarding.
    """
    fake_save_load = MagicMock()
    fake = _fake_mminion({"fake_returner.save_load": fake_save_load})
    with patch.dict(
        multi_returner.__opts__, {multi_returner.CONFIG_KEY: ["fake_returner"]}
    ):
        with patch.object(multi_returner, "_mminion", return_value=fake):
            multi_returner.save_load(
                "20260608000000000003",
                {"cmd": "publish", "jid": "20260608000000000003"},
                minions=["minion-a"],
            )

    fake_save_load.assert_called_once_with(
        "20260608000000000003",
        {"cmd": "publish", "jid": "20260608000000000003"},
        ["minion-a"],
    )


def test_get_jids_filter_dispatches_under_canonical_plural_name():
    """
    PR #67880: ``get_jids_filter`` (plural) is the canonical Salt name —
    ``salt/runners/jobs.py`` looks up ``<returner>.get_jids_filter`` and
    ``salt/returners/local_cache.py`` implements ``get_jids_filter``.
    The dispatcher and its ``fstr`` lookup must both use the plural form,
    otherwise the function is unreachable.
    """
    local_cache_filter = MagicMock(return_value={"jid-1": {"Function": "test.ping"}})
    fake_filter = MagicMock(return_value={"jid-2": {"Function": "cmd.run"}})
    fake = _fake_mminion(
        {
            "local_cache.get_jids_filter": local_cache_filter,
            "fake_returner.get_jids_filter": fake_filter,
        }
    )
    with patch.object(multi_returner, "_mminion", return_value=fake):
        ret = multi_returner.get_jids_filter(5, filter_find_job=False)

    local_cache_filter.assert_called_once_with(5, False)
    fake_filter.assert_called_once_with(5, False)
    assert ret == {
        "jid-1": {"Function": "test.ping"},
        "jid-2": {"Function": "cmd.run"},
    }


def test_get_jids_filter_attribute_exists_under_plural_name():
    """
    The module-level public name is what the loader exposes. A typo in the
    function name (singular ``get_jid_filter``) would break the runner
    integration even if the body were correct.
    """
    assert hasattr(multi_returner, "get_jids_filter")
    assert not hasattr(multi_returner, "get_jid_filter")


def test_save_reg_writes_to_every_configured_returner():
    """
    PR #67880: previously ``save_reg`` ``return``-ed after the first match
    so any returner past index 0 was silently skipped. This pins the
    write-to-all contract that the rest of the module follows.
    """
    local_cache_save_reg = MagicMock()
    fake_save_reg = MagicMock()
    fake = _fake_mminion(
        {
            "local_cache.save_reg": local_cache_save_reg,
            "fake_returner.save_reg": fake_save_reg,
        }
    )
    payload = {"event": "thorium.fire"}
    with patch.object(multi_returner, "_mminion", return_value=fake):
        multi_returner.save_reg(payload)

    local_cache_save_reg.assert_called_once_with(payload)
    fake_save_reg.assert_called_once_with(payload)


def test_save_reg_skips_returners_without_save_reg():
    """
    Returners that don't implement ``save_reg`` are skipped — the
    ``fstr in _mminion().returners`` guard must remain in place.
    """
    local_cache_save_reg = MagicMock()
    fake = _fake_mminion({"local_cache.save_reg": local_cache_save_reg})
    # fake_returner has NO save_reg entry
    with patch.object(multi_returner, "_mminion", return_value=fake):
        multi_returner.save_reg({"event": "thorium.fire"})

    local_cache_save_reg.assert_called_once()
