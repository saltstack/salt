import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_key(salt_key_cli, salt_minion):
    """
    Test running salt-key -L
    """
    ret = salt_key_cli.run("-L")
    assert ret.data
    assert salt_minion.id in ret.data["minions"]
