"""
Tests for the win_pkg module
"""
import logging

import pytest

import salt.modules.config as config
import salt.modules.pkg_resource as pkg_resource
import salt.modules.win_pkg as win_pkg
import salt.utils.data
import salt.utils.platform
import salt.utils.win_reg as win_reg
from salt.exceptions import MinionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    pkg_info = {
        "3.03": {
            "full_name": "Nullsoft Install System",
            "installer": "http://download.sourceforge.net/project/nsis/NSIS%203/3.03/nsis-3.03-setup.exe",
            "install_flags": "/S",
            "uninstaller": "%PROGRAMFILES(x86)%\\NSIS\\uninst-nsis.exe",
            "uninstall_flags": "/S",
            "msiexec": False,
            "reboot": False,
        },
        "3.02": {
            "full_name": "Nullsoft Install System",
            "installer": "http://download.sourceforge.net/project/nsis/NSIS%203/3.02/nsis-3.02-setup.exe",
            "install_flags": "/S",
            "uninstaller": "%PROGRAMFILES(x86)%\\NSIS\\uninst-nsis.exe",
            "uninstall_flags": "/S",
            "msiexec": False,
            "reboot": False,
        },
    }

    return {
        win_pkg: {
            "_get_latest_package_version": MagicMock(return_value="3.03"),
            "_get_package_info": MagicMock(return_value=pkg_info),
            "__salt__": {
                "pkg_resource.add_pkg": pkg_resource.add_pkg,
                "pkg_resource.parse_targets": pkg_resource.parse_targets,
                "pkg_resource.sort_pkglist": pkg_resource.sort_pkglist,
                "pkg_resource.stringify": pkg_resource.stringify,
                "config.valid_fileproto": config.valid_fileproto,
            },
            "__utils__": {
                "reg.key_exists": win_reg.key_exists,
                "reg.list_keys": win_reg.list_keys,
                "reg.read_value": win_reg.read_value,
                "reg.value_exists": win_reg.value_exists,
            },
        },
        pkg_resource: {"__grains__": {"os": "Windows"}},
    }


def test_pkg__get_reg_software():
    result = win_pkg._get_reg_software()
    assert isinstance(result, dict)
    found_python = False
    search = "Python 3"
    for key in result:
        if search in key:
            found_python = True
    assert found_python


def test_pkg__get_reg_software_noremove():
    search = "test_pkg_noremove"
    key = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{}".format(search)
    win_reg.set_value(hive="HKLM", key=key, vname="DisplayName", vdata=search)
    win_reg.set_value(hive="HKLM", key=key, vname="DisplayVersion", vdata="1.0.0")
    win_reg.set_value(
        hive="HKLM", key=key, vname="NoRemove", vtype="REG_DWORD", vdata="1"
    )
    try:
        result = win_pkg._get_reg_software()
        assert isinstance(result, dict)
        found = False
        search = "test_pkg"
        for item in result:
            if search in item:
                found = True
        assert found is True
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=key)
        assert not win_reg.key_exists(hive="HKLM", key=key)


def test_pkg__get_reg_software_noremove_not_present():
    search = "test_pkg_noremove_not_present"
    key = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{}".format(search)
    win_reg.set_value(hive="HKLM", key=key, vname="DisplayName", vdata=search)
    win_reg.set_value(hive="HKLM", key=key, vname="DisplayVersion", vdata="1.0.0")
    try:
        result = win_pkg._get_reg_software()
        assert isinstance(result, dict)
        found = False
        for item in result:
            if search in item:
                found = True
        assert found is False
    finally:
        win_reg.delete_key_recursive(hive="HKLM", key=key)
        assert not win_reg.key_exists(hive="HKLM", key=key)


def test_pkg_install_not_found():
    """
    Test pkg.install when the Version is NOT FOUND in the Software
    Definition
    """
    ret_reg = {"Nullsoft Install System": "3.03"}
    # The 2nd time it's run with stringify
    se_list_pkgs = {"nsis": ["3.03"]}
    with patch.object(win_pkg, "list_pkgs", return_value=se_list_pkgs), patch.object(
        win_pkg, "_get_reg_software", return_value=ret_reg
    ):
        expected = {"nsis": {"not found": "3.01"}}
        result = win_pkg.install(name="nsis", version="3.01")
        assert expected == result


def test_pkg_install_rollback():
    """
    test pkg.install rolling back to a previous version
    """
    ret_reg = {"Nullsoft Install System": "3.03"}
    # The 2nd time it's run, pkg.list_pkgs uses with stringify
    se_list_pkgs = [{"nsis": ["3.03"]}, {"nsis": "3.02"}]
    with patch.object(win_pkg, "list_pkgs", side_effect=se_list_pkgs), patch.object(
        win_pkg, "_get_reg_software", return_value=ret_reg
    ), patch.dict(
        win_pkg.__salt__, {"cp.is_cached": MagicMock(return_value=False)}
    ), patch.dict(
        win_pkg.__salt__,
        {"cp.cache_file": MagicMock(return_value="C:\\fake\\path.exe")},
    ), patch.dict(
        win_pkg.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        expected = {"nsis": {"new": "3.02", "old": "3.03"}}
        result = win_pkg.install(name="nsis", version="3.02")
        assert expected == result


def test_pkg_install_existing():
    """
    test pkg.install when the package is already installed
    no version passed
    """
    ret_reg = {"Nullsoft Install System": "3.03"}
    # The 2nd time it's run, pkg.list_pkgs uses with stringify
    se_list_pkgs = {"nsis": ["3.03"]}
    with patch.object(win_pkg, "list_pkgs", return_value=se_list_pkgs), patch.object(
        win_pkg, "_get_reg_software", return_value=ret_reg
    ), patch.dict(
        win_pkg.__salt__, {"cp.is_cached": MagicMock(return_value=False)}
    ), patch.dict(
        win_pkg.__salt__,
        {"cp.cache_file": MagicMock(return_value="C:\\fake\\path.exe")},
    ), patch.dict(
        win_pkg.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        expected = {}
        result = win_pkg.install(name="nsis")
        assert expected == result


def test_pkg_install_existing_with_version():
    """
    test pkg.install when the package is already installed
    A version is passed
    """
    ret_reg = {"Nullsoft Install System": "3.03"}
    # The 2nd time it's run, pkg.list_pkgs uses with stringify
    se_list_pkgs = {"nsis": ["3.03"]}
    with patch.object(win_pkg, "list_pkgs", return_value=se_list_pkgs), patch.object(
        win_pkg, "_get_reg_software", return_value=ret_reg
    ), patch.dict(
        win_pkg.__salt__, {"cp.is_cached": MagicMock(return_value=False)}
    ), patch.dict(
        win_pkg.__salt__,
        {"cp.cache_file": MagicMock(return_value="C:\\fake\\path.exe")},
    ), patch.dict(
        win_pkg.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        expected = {}
        result = win_pkg.install(name="nsis", version="3.03")
        assert expected == result


def test_pkg_install_name():
    """
    test pkg.install name extra_install_flags
    """

    ret__get_package_info = {
        "3.03": {
            "uninstaller": "%program.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "runme.exe",
            "uninstall_flags": "/S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    mock_cmd_run_all = MagicMock(return_value={"retcode": 0})
    with patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": MagicMock(
                return_value=[{"firebox": "3.03"}, None]
            ),
            "cp.is_cached": MagicMock(return_value="C:\\fake\\path.exe"),
            "cmd.run_all": mock_cmd_run_all,
        },
    ):
        ret = win_pkg.install(
            name="firebox",
            version="3.03",
            extra_install_flags="-e True -test_flag True",
        )
        assert "-e True -test_flag True" in str(mock_cmd_run_all.call_args[0])


def test_pkg_install_single_pkg():
    """
    test pkg.install pkg with extra_install_flags
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "%program.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "runme.exe",
            "uninstall_flags": "/S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    mock_cmd_run_all = MagicMock(return_value={"retcode": 0})
    with patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": MagicMock(
                return_value=[{"firebox": "3.03"}, None]
            ),
            "cp.is_cached": MagicMock(return_value="C:\\fake\\path.exe"),
            "cmd.run_all": mock_cmd_run_all,
        },
    ):
        ret = win_pkg.install(
            pkgs=["firebox"],
            version="3.03",
            extra_install_flags="-e True -test_flag True",
        )
        assert "-e True -test_flag True" in str(mock_cmd_run_all.call_args[0])


def test_pkg_install_log_message(caplog):
    """
    test pkg.install pkg with extra_install_flags
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "%program.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "runme.exe",
            "uninstall_flags": "/S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    mock_cmd_run_all = MagicMock(return_value={"retcode": 0})
    with patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": MagicMock(
                return_value=[{"firebox": "3.03"}, None]
            ),
            "cp.is_cached": MagicMock(return_value="C:\\fake\\path.exe"),
            "cmd.run_all": mock_cmd_run_all,
        },
    ), caplog.at_level(
        logging.DEBUG
    ):
        win_pkg.install(
            pkgs=["firebox"],
            version="3.03",
            extra_install_flags="-e True -test_flag True",
        )
        assert (
            'PKG : cmd: C:\\WINDOWS\\system32\\cmd.exe /s /c "runme.exe" /s -e '
            "True -test_flag True"
        ).lower() in [x.lower() for x in caplog.messages]
        assert "PKG : pwd: ".lower() in [x.lower() for x in caplog.messages]
        assert "PKG : retcode: 0" in caplog.messages


def test_pkg_install_multiple_pkgs():
    """
    test pkg.install pkg with extra_install_flags
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "%program.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "runme.exe",
            "uninstall_flags": "/S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    mock_cmd_run_all = MagicMock(return_value={"retcode": 0})
    with patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": MagicMock(
                return_value=[{"firebox": "3.03", "got": "3.03"}, None]
            ),
            "cp.is_cached": MagicMock(return_value="C:\\fake\\path.exe"),
            "cmd.run_all": mock_cmd_run_all,
        },
    ):
        ret = win_pkg.install(
            pkgs=["firebox", "got"], extra_install_flags="-e True -test_flag True"
        )
        assert "-e True -test_flag True" not in str(mock_cmd_run_all.call_args[0])


def test_pkg_install_minion_error_https():
    """
    Test pkg.install when cp.cache_file encounters a minion error
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "%program.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "https://repo.test.com/runme.exe",
            "uninstall_flags": "/S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    err_msg = (
        "Error: [Errno 11001] getaddrinfo failed reading"
        " https://repo.test.com/runme.exe"
    )
    mock_none = MagicMock(return_value=None)
    mock_minion_error = MagicMock(side_effect=MinionError(err_msg))
    mock_parse = MagicMock(return_value=[{"firebox": "3.03"}, None])
    with patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": mock_parse,
            "cp.is_cached": mock_none,
            "cp.cache_file": mock_minion_error,
        },
    ):
        ret = win_pkg.install(
            name="firebox",
            version="3.03",
        )
        expected = (
            "Failed to cache https://repo.test.com/runme.exe\nError: [Errno 11001]"
            " getaddrinfo failed reading https://repo.test.com/runme.exe"
        )

        assert ret == expected


def test_pkg_install_minion_error_salt():
    """
    Test pkg.install when cp.cache_file encounters a minion error
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "%program.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "salt://software/runme.exe",
            "uninstall_flags": "/S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    err_msg = "Error: [Errno 1] failed reading salt://software/runme.exe"
    mock_none = MagicMock(return_value=None)
    mock_minion_error = MagicMock(side_effect=MinionError(err_msg))
    mock_parse = MagicMock(return_value=[{"firebox": "3.03"}, None])
    with patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": mock_parse,
            "cp.is_cached": mock_none,
            "cp.cache_file": mock_minion_error,
        },
    ):
        ret = win_pkg.install(
            name="firebox",
            version="3.03",
        )
        expected = (
            "Failed to cache salt://software/runme.exe\n"
            "Error: [Errno 1] failed reading salt://software/runme.exe"
        )

        assert ret == expected


def test_pkg_install_minion_error_salt_cache_dir():
    """
    Test pkg.install when cp.cache_dir encounters a minion error
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "%program.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "salt://software/runme.exe",
            "cache_dir": True,
            "uninstall_flags": "/S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    err_msg = "Error: [Errno 1] failed reading salt://software"
    mock_none = MagicMock(return_value=None)
    mock_minion_error = MagicMock(side_effect=MinionError(err_msg))
    mock_parse = MagicMock(return_value=[{"firebox": "3.03"}, None])
    with patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {"cp.cache_dir": mock_minion_error},
    ):
        ret = win_pkg.install(
            name="firebox",
            version="3.03",
        )
        expected = (
            "Failed to cache salt://software\n"
            "Error: [Errno 1] failed reading salt://software"
        )

        assert ret == expected


def test_pkg_remove_minion_error_salt_cache_dir():
    """
    Test pkg.remove when cp.cache_dir encounters a minion error
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "salt://software/runme.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "salt://software/runme.exe",
            "cache_dir": True,
            "uninstall_flags": "/U /S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    err_msg = "Error: [Errno 1] failed reading salt://software"
    mock_minion_error = MagicMock(side_effect=MinionError(err_msg))
    mock_parse = MagicMock(return_value=[{"firebox": "3.03"}, None])
    se_list_pkgs = {"firebox": ["3.03"]}
    with patch.object(win_pkg, "list_pkgs", return_value=se_list_pkgs), patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": mock_parse,
            "cp.cache_dir": mock_minion_error,
        },
    ):
        ret = win_pkg.remove(name="firebox")
        expected = (
            "Failed to cache salt://software\n"
            "Error: [Errno 1] failed reading salt://software"
        )

        assert ret == expected


def test_pkg_remove_minion_error_salt():
    """
    Test pkg.remove when cp.cache_file encounters a minion error
    """
    ret__get_package_info = {
        "3.03": {
            "uninstaller": "salt://software/runme.exe",
            "reboot": False,
            "msiexec": False,
            "installer": "salt://software/runme.exe",
            "uninstall_flags": "/U /S",
            "locale": "en_US",
            "install_flags": "/s",
            "full_name": "Firebox 3.03 (x86 en-US)",
        }
    }

    err_msg = "Error: [Errno 1] failed reading salt://software/runme.exe"
    mock_minion_error = MagicMock(side_effect=MinionError(err_msg))
    mock_none = MagicMock(return_value=None)
    mock_parse = MagicMock(return_value=[{"firebox": "3.03"}, None])
    se_list_pkgs = {"firebox": ["3.03"]}
    with patch.object(win_pkg, "list_pkgs", return_value=se_list_pkgs), patch.object(
        salt.utils.data, "is_true", MagicMock(return_value=True)
    ), patch.object(
        win_pkg, "_get_package_info", MagicMock(return_value=ret__get_package_info)
    ), patch.dict(
        win_pkg.__salt__,
        {
            "pkg_resource.parse_targets": mock_parse,
            "cp.is_cached": mock_none,
            "cp.cache_file": mock_minion_error,
        },
    ):
        ret = win_pkg.remove(name="firebox")
        expected = (
            "Failed to cache salt://software/runme.exe\n"
            "Error: [Errno 1] failed reading salt://software/runme.exe"
        )

        assert ret == expected
