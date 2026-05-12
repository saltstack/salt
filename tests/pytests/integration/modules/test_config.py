import pytest


@pytest.mark.slow_test
def test_config_items(salt_cli, salt_minion):
    ret = salt_cli.run("config.items", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
