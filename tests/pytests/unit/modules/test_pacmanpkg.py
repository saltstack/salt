"""
    :codeauthor: Eric Vz <eric@base10.org>
"""

import pytest

import salt.modules.pacmanpkg as pacman
import salt.utils.systemd
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pacman: {}}


def test_list_pkgs():
    """
    Test if it list the packages currently installed in a dict
    """
    cmdmock = MagicMock(return_value="A 1.0\nB 2.0")
    sortmock = MagicMock()
    stringifymock = MagicMock()
    mock_ret = {"A": ["1.0"], "B": ["2.0"]}
    with patch.dict(
        pacman.__salt__,
        {
            "cmd.run": cmdmock,
            "pkg_resource.add_pkg": lambda pkgs, name, version: pkgs.setdefault(
                name, []
            ).append(version),
            "pkg_resource.sort_pkglist": sortmock,
            "pkg_resource.stringify": stringifymock,
        },
    ):
        assert pacman.list_pkgs() == mock_ret

    sortmock.assert_called_with(mock_ret)
    stringifymock.assert_called_with(mock_ret)


def test_list_pkgs_as_list():
    """
    Test if it lists the packages currently installed in a dict
    """
    cmdmock = MagicMock(return_value="A 1.0\nB 2.0")
    sortmock = MagicMock()
    stringifymock = MagicMock()
    mock_ret = {"A": ["1.0"], "B": ["2.0"]}
    with patch.dict(
        pacman.__salt__,
        {
            "cmd.run": cmdmock,
            "pkg_resource.add_pkg": lambda pkgs, name, version: pkgs.setdefault(
                name, []
            ).append(version),
            "pkg_resource.sort_pkglist": sortmock,
            "pkg_resource.stringify": stringifymock,
        },
    ):
        assert pacman.list_pkgs(True) == mock_ret

    sortmock.assert_called_with(mock_ret)
    assert stringifymock.call_count == 0


def test_list_pkgs_no_context():
    """
    Test if it list the packages currently installed in a dict
    """
    cmdmock = MagicMock(return_value="A 1.0\nB 2.0")
    sortmock = MagicMock()
    stringifymock = MagicMock()
    mock_ret = {"A": ["1.0"], "B": ["2.0"]}
    with patch.dict(
        pacman.__salt__,
        {
            "cmd.run": cmdmock,
            "pkg_resource.add_pkg": lambda pkgs, name, version: pkgs.setdefault(
                name, []
            ).append(version),
            "pkg_resource.sort_pkglist": sortmock,
            "pkg_resource.stringify": stringifymock,
        },
    ), patch.object(pacman, "_list_pkgs_from_context") as list_pkgs_context_mock:
        assert pacman.list_pkgs() == mock_ret

        pkgs = pacman.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        pkgs = pacman.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()


def test_group_list():
    """
    Test if it lists the available groups
    """

    def cmdlist(cmd, **kwargs):
        """
        Handle several different commands being run
        """
        if cmd == ["pacman", "-Sgg"]:
            return (
                "group-a pkg1\ngroup-a pkg2\ngroup-f pkg9\ngroup-c pkg3\ngroup-b pkg4"
            )
        elif cmd == ["pacman", "-Qg"]:
            return "group-a pkg1\ngroup-b pkg4"
        else:
            return f"Untested command ({cmd}, {kwargs})!"

    cmdmock = MagicMock(side_effect=cmdlist)

    sortmock = MagicMock()
    with patch.dict(
        pacman.__salt__, {"cmd.run": cmdmock, "pkg_resource.sort_pkglist": sortmock}
    ):
        assert pacman.group_list() == {
            "available": ["group-c", "group-f"],
            "installed": ["group-b"],
            "partially_installed": ["group-a"],
        }


def test_group_info():
    """
    Test if it shows the packages in a group
    """

    def cmdlist(cmd, **kwargs):
        """
        Handle several different commands being run
        """
        if cmd == ["pacman", "-Sgg", "testgroup"]:
            return "testgroup pkg1\ntestgroup pkg2"
        else:
            return f"Untested command ({cmd}, {kwargs})!"

    cmdmock = MagicMock(side_effect=cmdlist)

    sortmock = MagicMock()
    with patch.dict(
        pacman.__salt__, {"cmd.run": cmdmock, "pkg_resource.sort_pkglist": sortmock}
    ):
        assert pacman.group_info("testgroup")["default"] == ["pkg1", "pkg2"]


def test_group_diff():
    """
    Test if it shows the difference between installed and target group contents
    """

    listmock = MagicMock(return_value={"A": ["1.0"], "B": ["2.0"]})
    groupmock = MagicMock(
        return_value={
            "mandatory": [],
            "optional": [],
            "default": ["A", "C"],
            "conditional": [],
        }
    )
    with patch.dict(
        pacman.__salt__, {"pkg.list_pkgs": listmock, "pkg.group_info": groupmock}
    ):
        results = pacman.group_diff("testgroup")
        assert results["default"] == {"installed": ["A"], "not installed": ["C"]}


def test_pacman_install_sysupgrade_flag():
    """
    Test if the pacman.install function appends the '-u' flag only when sysupgrade is True
    """
    mock_parse_targets = MagicMock(return_value=({"somepkg": None}, "repository"))
    mock_has_scope = MagicMock(return_value=False)
    mock_list_pkgs = MagicMock(return_value={"somepkg": "1.0"})
    mock_run_all = MagicMock(return_value={"retcode": 0, "stderr": ""})

    with patch.dict(
        pacman.__salt__,
        {
            "cmd.run_all": mock_run_all,
            "pkg_resource.parse_targets": mock_parse_targets,
            "config.get": MagicMock(return_value=True),
        },
    ), patch.object(salt.utils.systemd, "has_scope", mock_has_scope), patch.object(
        pacman, "list_pkgs", mock_list_pkgs
    ):
        pacman.install(name="somepkg", sysupgrade=True)
        args, _ = pacman.__salt__["cmd.run_all"].call_args
        assert "-u" in args[0]

        pacman.install(name="somepkg", sysupgrade=None, refresh=True)
        args, _ = pacman.__salt__["cmd.run_all"].call_args
        assert "-u" not in args[0]
