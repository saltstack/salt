import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


def test_grains_items(salt_cli, salt_minion, salt_master):
    """
    Test grains.items
    """
    assert salt_master.is_running()

    ret = salt_cli.run("grains.items", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "osrelease" in ret.data


def test_grains_item_os(salt_cli, salt_minion, salt_master):
    """
    Test grains.item os
    """
    assert salt_master.is_running()

    ret = salt_cli.run("grains.item", "os", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "os" in ret.data


def test_grains_item_pythonversion(salt_cli, salt_minion, salt_master):
    """
    Test grains.item pythonversion
    """
    assert salt_master.is_running()

    ret = salt_cli.run("grains.item", "pythonversion", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "pythonversion" in ret.data


def test_grains_setval_key_val(salt_cli, salt_minion, salt_master):
    """
    Test grains.setval key val
    """
    assert salt_master.is_running()

    ret = salt_cli.run("grains.setval", "key", "val", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "key" in ret.data
