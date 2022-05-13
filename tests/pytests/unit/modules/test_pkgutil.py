"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import pytest
import salt.modules.pkgutil as pkgutil
import salt.utils.pkg
from salt.exceptions import CommandExecutionError, MinionError
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {pkgutil: {}}


# 'refresh_db' function tests: 1


def test_refresh_db():
    """
    Test if it updates the pkgutil repo database (pkgutil -U).
    """
    mock = MagicMock(return_value=0)
    with patch.dict(pkgutil.__salt__, {"cmd.retcode": mock}):
        with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
            assert pkgutil.refresh_db()


# 'upgrade_available' function tests: 1


def test_upgrade_available():
    """
    Test if there is an upgrade available for a certain package.
    """
    mock = MagicMock(return_value="A\n B\n SAME")
    with patch.dict(pkgutil.__salt__, {"cmd.run_stdout": mock}):
        assert pkgutil.upgrade_available("CSWpython") == ""

    mock = MagicMock(side_effect=["A\n B\n SALT", None])
    with patch.dict(pkgutil.__salt__, {"cmd.run_stdout": mock}):
        assert pkgutil.upgrade_available("CSWpython") == "SALT"

        assert pkgutil.upgrade_available("CSWpython") == ""


# 'list_upgrades' function tests: 1


def test_list_upgrades():
    """
    Test if it list all available package upgrades on this system.
    """
    mock_run = MagicMock(return_value="A\t B\t SAME")
    mock_ret = MagicMock(return_value=0)
    with patch.dict(
        pkgutil.__salt__, {"cmd.run_stdout": mock_run, "cmd.retcode": mock_ret}
    ):
        with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
            assert pkgutil.list_upgrades() == {"A": " B"}


# 'upgrade' function tests: 1


def test_upgrade():
    """
    Test if it upgrade all of the packages to the latest available version.
    """
    mock_run = MagicMock(return_value="A\t B\t SAME")
    mock_ret = MagicMock(return_value=0)
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        pkgutil.__salt__,
        {
            "cmd.run_stdout": mock_run,
            "cmd.retcode": mock_ret,
            "pkg_resource.stringify": mock_pkg,
            "pkg_resource.sort_pkglist": mock_pkg,
            "cmd.run_all": mock_ret,
            "cmd.run": mock_run,
        },
    ):
        with patch.dict(pkgutil.__context__, {"pkg.list_pkgs": mock_ret}):
            with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
                assert pkgutil.upgrade() == {}


# 'list_pkgs' function tests: 1


def test_list_pkgs():
    """
    Test if it list the packages currently installed as a dict.
    """
    mock_run = MagicMock(return_value="A\t B\t SAME")
    mock_ret = MagicMock(return_value=True)
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        pkgutil.__salt__,
        {
            "cmd.run_stdout": mock_run,
            "cmd.retcode": mock_ret,
            "pkg_resource.stringify": mock_pkg,
            "pkg_resource.sort_pkglist": mock_pkg,
            "cmd.run": mock_run,
        },
    ):
        with patch.dict(pkgutil.__context__, {"pkg.list_pkgs": mock_ret}):
            assert pkgutil.list_pkgs(versions_as_list=True, removed=True) == {}

        assert pkgutil.list_pkgs() == {}

    with patch.dict(pkgutil.__context__, {"pkg.list_pkgs": True}):
        assert pkgutil.list_pkgs(versions_as_list=True)

        mock_pkg = MagicMock(return_value=True)
        with patch.dict(pkgutil.__salt__, {"pkg_resource.stringify": mock_pkg}):
            assert pkgutil.list_pkgs()


def test_list_pkgs_no_context():
    """
    Test if it list the packages currently installed as a dict.
    """
    mock_run = MagicMock(return_value="A\t B\t SAME")
    mock_ret = MagicMock(return_value=True)
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        pkgutil.__salt__,
        {
            "cmd.run_stdout": mock_run,
            "cmd.retcode": mock_ret,
            "pkg_resource.stringify": mock_pkg,
            "pkg_resource.sort_pkglist": mock_pkg,
            "cmd.run": mock_run,
        },
    ), patch.object(pkgutil, "_list_pkgs_from_context") as list_pkgs_context_mock:
        pkgs = pkgutil.list_pkgs(versions_as_list=True, removed=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        pkgs = pkgutil.list_pkgs(versions_as_list=True, removed=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()


# 'version' function tests: 1


def test_version():
    """
    Test if it returns a version if the package is installed.
    """
    mock_ret = MagicMock(return_value=True)
    with patch.dict(pkgutil.__salt__, {"pkg_resource.version": mock_ret}):
        assert pkgutil.version("CSWpython")


# 'latest_version' function tests: 1


def test_latest_version():
    """
    Test if it return the latest version of the named package
    available for upgrade or installation.
    """
    assert pkgutil.latest_version() == ""

    mock_run_all = MagicMock(return_value="A\t B\t SAME")
    mock_run = MagicMock(return_value={"stdout": ""})
    mock_ret = MagicMock(return_value=True)
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        pkgutil.__salt__,
        {
            "cmd.retcode": mock_ret,
            "pkg_resource.stringify": mock_pkg,
            "pkg_resource.sort_pkglist": mock_pkg,
            "cmd.run_all": mock_run,
            "cmd.run": mock_run_all,
        },
    ):
        with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
            assert pkgutil.latest_version("CSWpython") == ""

            assert pkgutil.latest_version("CSWpython", "Python") == {
                "Python": "",
                "CSWpython": "",
            }


# 'install' function tests: 1


def test_install():
    """
    Test if it install packages using the pkgutil tool.
    """
    mock_pkg = MagicMock(side_effect=MinionError)
    with patch.dict(pkgutil.__salt__, {"pkg_resource.parse_targets": mock_pkg}):
        pytest.raises(CommandExecutionError, pkgutil.install)

    mock_ret = MagicMock(return_value=True)
    mock_pkg = MagicMock(return_value=[""])
    with patch.dict(pkgutil.__salt__, {"pkg_resource.parse_targets": mock_pkg}):
        with patch.dict(pkgutil.__context__, {"pkg.list_pkgs": mock_ret}):
            assert pkgutil.install() == {}

    mock_run = MagicMock(return_value="A\t B\t SAME")
    mock_run_all = MagicMock(return_value={"stdout": ""})
    mock_pkg = MagicMock(return_value=[{"bar": "1.2.3"}])
    with patch.dict(
        pkgutil.__salt__,
        {
            "pkg_resource.parse_targets": mock_pkg,
            "pkg_resource.stringify": mock_pkg,
            "pkg_resource.sort_pkglist": mock_pkg,
            "cmd.run_all": mock_run_all,
            "cmd.run": mock_run,
        },
    ):
        with patch.dict(pkgutil.__context__, {"pkg.list_pkgs": mock_ret}):
            assert pkgutil.install(pkgs='["foo", {"bar": "1.2.3"}]') == {}


# 'remove' function tests: 1


def test_remove():
    """
    Test if it remove a package and all its dependencies
    which are not in use by other packages.
    """
    mock_pkg = MagicMock(side_effect=MinionError)
    with patch.dict(pkgutil.__salt__, {"pkg_resource.parse_targets": mock_pkg}):
        pytest.raises(CommandExecutionError, pkgutil.remove)

    mock_ret = MagicMock(return_value=True)
    mock_run = MagicMock(return_value="A\t B\t SAME")
    mock_run_all = MagicMock(return_value={"stdout": ""})
    mock_pkg = MagicMock(return_value=[""])
    with patch.dict(
        pkgutil.__salt__,
        {
            "pkg_resource.parse_targets": mock_pkg,
            "pkg_resource.stringify": mock_pkg,
            "pkg_resource.sort_pkglist": mock_pkg,
            "cmd.run_all": mock_run_all,
            "cmd.run": mock_run,
        },
    ):
        with patch.dict(pkgutil.__context__, {"pkg.list_pkgs": mock_ret}):
            assert pkgutil.remove() == {}

    mock_pkg = MagicMock(return_value=[{"bar": "1.2.3"}])
    with patch.dict(
        pkgutil.__salt__,
        {
            "pkg_resource.parse_targets": mock_pkg,
            "pkg_resource.stringify": mock_pkg,
            "pkg_resource.sort_pkglist": mock_pkg,
            "cmd.run_all": mock_run_all,
            "cmd.run": mock_run,
        },
    ):
        with patch.dict(pkgutil.__context__, {"pkg.list_pkgs": mock_ret}):
            with patch.object(pkgutil, "list_pkgs", return_value={"bar": "1.2.3"}):
                assert pkgutil.remove(pkgs='["foo", "bar"]') == {}


# 'purge' function tests: 1


def test_purge():
    """
    Test if it package purges are not supported,
    this function is identical to ``remove()``.
    """
    mock_pkg = MagicMock(side_effect=MinionError)
    with patch.dict(pkgutil.__salt__, {"pkg_resource.parse_targets": mock_pkg}):
        pytest.raises(CommandExecutionError, pkgutil.purge)
