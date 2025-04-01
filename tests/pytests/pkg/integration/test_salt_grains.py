import packaging.version
import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
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


def test_grains_package_onedir(salt_cli, salt_minion, install_salt):
    """
    Test that the package grain returns onedir
    """
    # This grain was added in 3007.0
    if packaging.version.parse(install_salt.version) < packaging.version.parse(
        "3007.0"
    ):
        pytest.skip(
            "The package grain is only going to equal 'onedir' in version 3007.0 or later"
        )
    ret = salt_cli.run("grains.get", "package", minion_tgt=salt_minion.id)
    assert ret.data == "onedir"
    assert ret.data, ret
