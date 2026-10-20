"""
Integration regression tests for ``salt-run manage.status`` /
``manage.up`` / ``manage.down``.

The bug fixed by this module (issue #69582): ``manage._ping`` was
treating the synthesized ``no_return`` rows yielded by
``LocalClient.get_cli_event_returns`` (now emitted by default with
``expect_minions=True``) as successful returns. That made
``manage.status`` report every targeted minion as up and
``manage.down`` return nothing, even when a known-accepted minion was
not running.

These tests exercise the real runner against live salt-minions plus a
fake accepted-but-absent minion key, so the bug reproduces end to end
without mocks.
"""

import logging
import os
import shutil

import pytest

import salt.utils.path

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


FAKE_DOWN_MINION_ID = "down-minion-69582"


@pytest.fixture
def fake_down_minion(salt_master, salt_minion):
    """
    Make the master treat ``down-minion-69582`` as an accepted minion by
    cloning ``salt_minion``'s public key under the fake id. No daemon
    will respond on that id so any targeting call should time it out --
    which is exactly what ``manage.down`` should surface.
    """
    accepted = salt.utils.path.join(
        salt_master.config["pki_dir"], "minions", salt_minion.id
    )
    fake = salt.utils.path.join(
        salt_master.config["pki_dir"], "minions", FAKE_DOWN_MINION_ID
    )
    shutil.copyfile(accepted, fake)
    try:
        yield FAKE_DOWN_MINION_ID
    finally:
        try:
            os.remove(fake)
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.error(
                "Failed to remove %s, this may affect other tests: %s",
                fake,
                exc,
            )


def _no_return_marker_in(result):
    """
    Verify the runner never emitted a synthesized ``no_return`` payload
    in a slot that should hold a minion id. This is the original
    user-visible symptom of #69582: ``manage.up`` was returning entries
    whose ids were actually timeout placeholders.
    """
    if isinstance(result, dict):
        values = list(result.values())
        keys = list(result.keys())
    else:
        values = list(result)
        keys = list(result)
    for slot in keys + values:
        if isinstance(slot, str) and "no_return" in slot.lower():
            return True
        if isinstance(slot, dict) and slot.get("out") == "no_return":
            return True
    return False


def test_manage_status_partitions_live_and_down_minions(
    salt_run_cli, salt_minion, salt_sub_minion, fake_down_minion
):
    """
    ``salt-run manage.status`` must list live minions in ``up`` and the
    fake accepted-but-absent minion in ``down``.

    Regression for https://github.com/saltstack/salt/issues/69582
    where the result was ``{"up": [<everything>], "down": []}``.
    """
    ret = salt_run_cli.run(
        "manage.status", "timeout=5", "gather_job_timeout=10", _timeout=120
    )
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, dict), data
    assert set(data.keys()) == {"up", "down"}, data
    up = data["up"] or []
    down = data["down"] or []
    assert salt_minion.id in up, data
    assert salt_sub_minion.id in up, data
    assert fake_down_minion in down, data
    assert fake_down_minion not in up, data
    assert salt_minion.id not in down, data
    assert salt_sub_minion.id not in down, data
    assert not _no_return_marker_in(up), data
    assert not _no_return_marker_in(down), data


def test_manage_up_excludes_down_minions(
    salt_run_cli, salt_minion, salt_sub_minion, fake_down_minion
):
    """
    ``salt-run manage.up`` must omit minions that never returned.
    Before the fix the fake accepted-but-absent minion was reported as
    up because the synthesized ``no_return`` row was counted as a
    successful return.
    """
    ret = salt_run_cli.run(
        "manage.up", "timeout=5", "gather_job_timeout=10", _timeout=120
    )
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, list), data
    assert salt_minion.id in data, data
    assert salt_sub_minion.id in data, data
    assert fake_down_minion not in data, data
    assert not _no_return_marker_in(data), data


def test_manage_down_includes_unresponsive_minions(
    salt_run_cli, salt_minion, salt_sub_minion, fake_down_minion
):
    """
    ``salt-run manage.down`` must list the fake accepted-but-absent
    minion. Before the fix it returned an empty list regardless of how
    many accepted minions were offline.
    """
    ret = salt_run_cli.run(
        "manage.down", "timeout=5", "gather_job_timeout=10", _timeout=120
    )
    assert ret.returncode == 0, ret
    data = ret.data
    assert isinstance(data, list), data
    assert fake_down_minion in data, data
    assert salt_minion.id not in data, data
    assert salt_sub_minion.id not in data, data
    assert not _no_return_marker_in(data), data
