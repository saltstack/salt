import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_pillar(salt_cli, salt_minion):
    """
    Test pillar.items
    """
    ret = salt_cli.run("pillar.items", minion_tgt=salt_minion.id)
    assert "info" in ret.data
