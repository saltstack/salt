import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_grains_items(salt_cli, salt_minion):
    """
    Test grains.items
    """
    ret = salt_cli.run("grains.items", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "osrelease" in ret.data


def test_grains_item_os(salt_cli, salt_minion):
    """
    Test grains.item os
    """
    ret = salt_cli.run("grains.item", "os", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "os" in ret.data


def test_grains_item_pythonversion(salt_cli, salt_minion):
    """
    Test grains.item pythonversion
    """
    ret = salt_cli.run("grains.item", "pythonversion", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "pythonversion" in ret.data


def test_grains_setval_key_val(salt_cli, salt_minion):
    """
    Test grains.setval key val
    """
    ret = salt_cli.run("grains.setval", "key", "val", minion_tgt=salt_minion.id)
    assert ret.data, ret
    assert "key" in ret.data


def test_grains_package_onedir(salt_cli, salt_minion):
    """
    Test that the package grain returns onedir
    """
    ret = salt_cli.run("grains.get", "package", minion_tgt=salt_minion.id)
    assert ret.data == "onedir"
    assert ret.data, ret
