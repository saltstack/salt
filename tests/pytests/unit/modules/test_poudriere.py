"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import os

import pytest
import salt.modules.poudriere as poudriere
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {poudriere: {}}


def test_is_jail():
    """
    Test if it return True if jail exists False if not.
    """
    mock = MagicMock(return_value="salt stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.is_jail("salt")

        assert not poudriere.is_jail("SALT")


def test_make_pkgng_aware():
    """
    Test if it make jail ``jname`` pkgng aware.
    """
    temp_dir = os.path.join("tmp", "salt")
    conf_file = os.path.join("tmp", "salt", "salt-make.conf")
    ret1 = "Could not create or find required directory {}".format(temp_dir)
    ret2 = "Looks like file {} could not be created".format(conf_file)
    ret3 = {"changes": "Created {}".format(conf_file)}
    mock = MagicMock(return_value=temp_dir)
    mock_true = MagicMock(return_value=True)
    with patch.dict(
        poudriere.__salt__, {"config.option": mock, "file.write": mock_true}
    ):
        with patch.object(os.path, "isdir", MagicMock(return_value=False)):
            with patch.object(os, "makedirs", mock_true):
                assert poudriere.make_pkgng_aware("salt") == ret1

        with patch.object(os.path, "isdir", mock_true):
            assert poudriere.make_pkgng_aware("salt") == ret2

            with patch.object(os.path, "isfile", mock_true):
                assert poudriere.make_pkgng_aware("salt") == ret3


def test_parse_config():
    """
    Test if it returns a dict of poudriere main configuration definitions.
    """
    mock = MagicMock(return_value="/tmp/salt")
    with patch.dict(poudriere.__salt__, {"config.option": mock}), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch.object(
        poudriere, "_check_config_exists", MagicMock(side_effect=[True, False])
    ):
        assert poudriere.parse_config() == {}

        assert poudriere.parse_config() == "Could not find /tmp/salt on file system"


def test_version():
    """
    Test if it return poudriere version.
    """
    mock = MagicMock(return_value="9.0-RELEASE")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}):
        assert poudriere.version() == "9.0-RELEASE"


def test_list_jails():
    """
    Test if it return a list of current jails managed by poudriere.
    """
    mock = MagicMock(return_value="salt stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.list_jails() == ["salt stack"]


def test_list_ports():
    """
    Test if it return a list of current port trees managed by poudriere.
    """
    mock = MagicMock(return_value="salt stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.list_ports() == ["salt stack"]


def test_create_jail():
    """
    Test if it creates a new poudriere jail if one does not exist.
    """
    mock_stack = MagicMock(return_value="90amd64 stack")
    mock_true = MagicMock(return_value=True)
    with patch.dict(poudriere.__salt__, {"cmd.run": mock_stack}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.create_jail("90amd64", "amd64") == "90amd64 already exists"

        with patch.object(poudriere, "make_pkgng_aware", mock_true):
            assert (
                poudriere.create_jail("80amd64", "amd64")
                == "Issue creating jail 80amd64"
            )

    with patch.object(poudriere, "make_pkgng_aware", mock_true), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        with patch.object(poudriere, "is_jail", MagicMock(side_effect=[False, True])):
            with patch.dict(poudriere.__salt__, {"cmd.run": mock_stack}):
                assert (
                    poudriere.create_jail("80amd64", "amd64") == "Created jail 80amd64"
                )


def test_update_jail():
    """
    Test if it run freebsd-update on `name` poudriere jail.
    """
    mock = MagicMock(return_value="90amd64 stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.update_jail("90amd64") == "90amd64 stack"

        assert poudriere.update_jail("80amd64") == "Could not find jail 80amd64"


def test_delete_jail():
    """
    Test if it deletes poudriere jail with `name`.
    """
    ret = "Looks like there was an issue deleting jail 90amd64"
    mock_stack = MagicMock(return_value="90amd64 stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock_stack}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.delete_jail("90amd64") == ret

        assert (
            poudriere.delete_jail("80amd64")
            == "Looks like jail 80amd64 has not been created"
        )

    ret1 = 'Deleted jail "80amd64" but was unable to remove jail make file'
    with patch.object(
        poudriere, "is_jail", MagicMock(side_effect=[True, False, True, False])
    ):
        with patch.dict(poudriere.__salt__, {"cmd.run": mock_stack}):
            with patch.object(
                poudriere, "_config_dir", MagicMock(return_value="/tmp/salt")
            ):
                assert poudriere.delete_jail("80amd64") == "Deleted jail 80amd64"

                with patch.object(os.path, "isfile", MagicMock(return_value=True)):
                    assert poudriere.delete_jail("80amd64") == ret1


def test_create_ports_tree():
    """
    Test if it not working need to run portfetch non interactive.
    """
    mock = MagicMock(return_value="salt stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.create_ports_tree() == "salt stack"


def test_update_ports_tree():
    """
    Test if it updates the ports tree, either the default
    or the `ports_tree` specified.
    """
    mock = MagicMock(return_value="salt stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.update_ports_tree("staging") == "salt stack"


def test_bulk_build():
    """
    Test if it run bulk build on poudriere server.
    """
    ret = "Could not find file /root/pkg_list on filesystem"
    mock = MagicMock(return_value="salt stack")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.bulk_build("90amd64", "/root/pkg_list") == ret

        with patch.object(os.path, "isfile", MagicMock(return_value=True)):
            assert (
                poudriere.bulk_build("90amd64", "/root/pkg_list")
                == "Could not find jail 90amd64"
            )

    ret = "There may have been an issue building packages dumping output: 90amd64 stack"
    with patch.object(os.path, "isfile", MagicMock(return_value=True)), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        mock = MagicMock(return_value="90amd64 stack packages built")
        with patch.dict(poudriere.__salt__, {"cmd.run": mock}):
            assert (
                poudriere.bulk_build("90amd64", "/root/pkg_list")
                == "90amd64 stack packages built"
            )

        mock = MagicMock(return_value="90amd64 stack")
        with patch.dict(poudriere.__salt__, {"cmd.run": mock}):
            assert poudriere.bulk_build("90amd64", "/root/pkg_list") == ret


def test_info_jail():
    """
    Test to stdout the information poudriere jail with `name`.
    """
    ret = ["head-amd64"]
    mock_stack = MagicMock(return_value="head-amd64")
    with patch.dict(poudriere.__salt__, {"cmd.run": mock_stack}), patch(
        "salt.modules.poudriere._check_config_exists", MagicMock(return_value=True)
    ):
        assert poudriere.info_jail("head-amd64") == ret

        assert poudriere.info_jail("12-amd64") == "Could not find jail 12-amd64"

    ret1 = "Could not find jail 12-amd64"
    with patch.object(
        poudriere, "is_jail", MagicMock(side_effect=[True, False, True, False])
    ):
        with patch.dict(poudriere.__salt__, {"cmd.run": mock_stack}):
            with patch.object(
                poudriere, "_config_dir", MagicMock(return_value="/tmp/salt")
            ):
                assert poudriere.info_jail("12-amd64") == ["head-amd64"]

                with patch.object(os.path, "isfile", MagicMock(return_value=True)):
                    assert poudriere.info_jail("12-amd64") == ret1
