"""
integration tests for the mine runner
"""

import pytest

import salt.config
import salt.runners.mine as mine_runner
from tests.support.mock import patch


@pytest.fixture(scope="module")
def mine(runners):
    return runners.mine


@pytest.fixture(scope="module")
def minion_opts():
    return salt.config.minion_config(None)


@pytest.fixture(scope="module")
def pillar_tree(salt_master, salt_call_cli, salt_run_cli, salt_minion):
    top_file = """
    base:
      '*':
        - mine
    """

    mine_file = """
    mine_functions:
      test_fun:
        mine_function: cmd.run
        cmd: 'echo hello test'
      test_no_allow:
        mine_function: cmd.run
        cmd: 'echo hello no allow'
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    mine_tempfile = salt_master.pillar_tree.base.temp_file("mine.sls", mine_file)
    try:
        with top_tempfile, mine_tempfile:
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.returncode == 0
            assert ret.data is True
            ret = salt_run_cli.run("mine.update", salt_minion.id)
            assert ret.returncode == 0
            ret = salt_call_cli.run("pillar.items")
            assert ret.returncode == 0
            yield
    finally:
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        ret = salt_run_cli.run("mine.update", salt_minion.id)
        assert ret.returncode == 0


@pytest.mark.usefixtures("pillar_tree")
def test_allow_tgt(salt_run_cli, salt_minion, minion_opts):
    tgt = salt_minion.id
    fun = "test_fun"
    with patch("salt.runners.mine.__opts__", minion_opts, create=True):
        ret = mine_runner.get(tgt, fun)

    ret = salt_run_cli.run("mine.get", tgt, fun)
    assert ret.data == {salt_minion.id: "hello test"}


@pytest.mark.usefixtures("pillar_tree")
def test_no_allow_tgt(salt_run_cli, salt_minion):
    tgt = salt_minion.id
    fun = "test_no_allow"

    ret = salt_run_cli.run("mine.get", tgt, fun)
    assert ret.data == {salt_minion.id: "hello no allow"}
