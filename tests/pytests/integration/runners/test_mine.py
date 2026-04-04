"""
integration tests for the mine runner
"""

import time

import pytest


@pytest.fixture(scope="session")
def salt_minion_id():
    return "test-mine"


@pytest.fixture(scope="session")
def master_id():
    master_id = "test-mine"
    yield master_id


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
        allow_tgt: '*'
        allow_tgt_type: 'glob'
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
            # mine.update fires an event and sleeps 0.5s, but the master may need
            # additional time to process and store the mine data.  Poll until the
            # data is available so that tests don't race against propagation.
            # Use salt_call_cli (minion-side) so the allow_tgt ACL check passes
            # — the runner uses the master's ID which is not a minion target.
            for _ in range(10):
                ret = salt_call_cli.run("mine.get", salt_minion.id, "test_fun")
                if ret.data:
                    break
                time.sleep(1)
            ret = salt_call_cli.run("pillar.items")
            assert ret.returncode == 0
            yield
    finally:
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        ret = salt_run_cli.run("mine.update", salt_minion.id)
        assert ret.returncode == 0


@pytest.mark.usefixtures("pillar_tree", "master_id", "salt_minion_id")
def test_allow_tgt(salt_call_cli, salt_minion):
    """
    Test that mine.get returns data when allow_tgt permits the caller.
    Must use salt_call_cli (minion-side execution module) rather than
    salt_run_cli (runner), because the runner passes the master's ID as
    the caller and the master is not a minion target — it will never match
    the allow_tgt glob and the mine ACL will always deny access.
    """
    tgt = salt_minion.id
    fun = "test_fun"

    ret = salt_call_cli.run("mine.get", tgt, fun)
    assert ret.data == {salt_minion.id: "hello test"}


@pytest.mark.usefixtures("pillar_tree")
def test_no_allow_tgt(salt_run_cli, salt_minion):
    tgt = salt_minion.id
    fun = "test_no_allow"

    ret = salt_run_cli.run("mine.get", tgt, fun)
    assert ret.data == {salt_minion.id: "hello no allow"}
