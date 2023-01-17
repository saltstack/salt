import sys


def test_salt_state_file(salt_cli, salt_minion):
    """
    Test state file
    """
    if sys.platform.startswith("win"):
        ret = salt_cli.run("state.apply", "win_states", minion_tgt=salt_minion.id)
    else:
        ret = salt_cli.run("state.apply", "states", minion_tgt=salt_minion.id)

    assert ret.data, ret
    sls_ret = ret.data[next(iter(ret.data))]
    assert "changes" in sls_ret
    assert "name" in sls_ret
