"""
Tests for the salt-run command
"""

import logging

import pytest

pytestmark = [
    pytest.mark.slow_test,
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def pillar_tree(base_env_pillar_tree_root_dir, salt_minion, salt_sub_minion, salt_cli):
    top_file = """
    base:
      '{}':
        - basic
      '{}':
        - basic
    """.format(
        salt_minion.id, salt_sub_minion.id
    )
    basic_pillar_file = """
    monty: python
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    basic_tempfile = pytest.helpers.temp_file(
        "basic.sls", basic_pillar_file, base_env_pillar_tree_root_dir
    )
    try:
        with top_tempfile, basic_tempfile:
            ret = salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
            assert ret.returncode == 0
            assert salt_minion.id in ret.data
            assert ret.data[salt_minion.id] is True
            assert salt_sub_minion.id in ret.data
            assert ret.data[salt_sub_minion.id] is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
        assert ret.returncode == 0
        assert salt_minion.id in ret.data
        assert ret.data[salt_minion.id] is True
        assert salt_sub_minion.id in ret.data
        assert ret.data[salt_sub_minion.id] is True


def test_cache(salt_run_cli):
    """
    Store, list, fetch, then flush data
    """
    # Store the data
    ret = salt_run_cli.run(
        "cache.store",
        bank="cachetest/runner",
        key="test_cache",
        data="The time has come the walrus said",
    )
    assert ret.returncode == 0
    # Make sure we can see the new key
    ret = salt_run_cli.run("cache.list", bank="cachetest/runner")
    assert ret.returncode == 0
    assert "test_cache" in ret.data

    # Make sure we can see the new data
    ret = salt_run_cli.run("cache.fetch", bank="cachetest/runner", key="test_cache")
    assert ret.returncode == 0
    assert "The time has come the walrus said" in ret.stdout

    # Make sure we can delete the data
    ret = salt_run_cli.run("cache.flush", bank="cachetest/runner", key="test_cache")
    assert ret.returncode == 0

    ret = salt_run_cli.run("cache.list", bank="cachetest/runner")
    assert ret.returncode == 0
    assert "test_cache" not in ret.data


def test_cache_invalid(salt_run_cli):
    """
    Store, list, fetch, then flush data
    """
    ret = salt_run_cli.run("cache.store")
    assert ret.returncode == 0
    # Make sure we can see the new key
    assert "Passed invalid arguments:" in ret.stdout


def test_grains(salt_run_cli, pillar_tree, salt_minion):
    """
    Test cache.grains
    """
    ret = salt_run_cli.run("cache.grains", tgt=salt_minion.id)
    assert ret.returncode == 0
    assert salt_minion.id in ret.data


def test_pillar(salt_run_cli, pillar_tree, salt_minion, salt_sub_minion):
    """
    Test cache.pillar
    """
    ret = salt_run_cli.run("cache.pillar", tgt=salt_minion.id)
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_pillar_no_tgt(salt_run_cli, pillar_tree, salt_minion, salt_sub_minion):
    """
    Test cache.pillar when no tgt is
    supplied. This should return pillar
    data for all minions
    """
    ret = salt_run_cli.run("cache.pillar")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_pillar_minion_noexist(salt_run_cli, pillar_tree, salt_minion, salt_sub_minion):
    """
    Test cache.pillar when the target does not exist
    """
    ret = salt_run_cli.run("cache.pillar", tgt="non-exiting-minion")
    assert ret.returncode == 0
    assert salt_minion.id not in ret.data
    assert salt_sub_minion.id not in ret.data


def test_pillar_minion_tgt_type_pillar(
    salt_run_cli, pillar_tree, salt_minion, salt_sub_minion
):
    """
    Test cache.pillar when the target exists
    and tgt_type is pillar
    """
    ret = salt_run_cli.run("cache.pillar", tgt="monty:python", tgt_type="pillar")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_mine(salt_run_cli, salt_minion):
    """
    Test cache.mine
    """
    ret = salt_run_cli.run("cache.mine", tgt=salt_minion.id)
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
