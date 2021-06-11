import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.mark.slow_test
def test_sync_grains(salt_call_cli):
    ret = salt_call_cli.run("saltutil.sync_grains")
    assert ret.exitcode == 0
    assert ret.json == []
