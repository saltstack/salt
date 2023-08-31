import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.mark.slow_test
def test_sync_grains(salt_call_cli):
    ret = salt_call_cli.run("saltutil.sync_grains")
    assert ret.returncode == 0
    try:
        assert ret.data == []
    except AssertionError:
        # Maybe it had to sync again on the above call.
        # On this next call though, it shold return an empty list
        ret = salt_call_cli.run("saltutil.sync_grains")
        assert ret.returncode == 0
        assert ret.data == []
