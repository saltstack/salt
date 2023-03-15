import pytest

import salt.states.macpackage as macpackage
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {macpackage: {}}


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_pkg():
    """
    Test installing a PKG file
    """
    expected = {
        "changes": {"installed": ["some.other.id"]},
        "comment": "/path/to/file.pkg installed",
        "name": "/path/to/file.pkg",
        "result": True,
    }

    installed_mock = MagicMock(return_value=["com.apple.id"])
    get_pkg_id_mock = MagicMock(return_value=["some.other.id"])
    install_mock = MagicMock(return_value={"retcode": 0})

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.installed_pkgs": installed_mock,
            "macpackage.get_pkg_id": get_pkg_id_mock,
            "macpackage.install": install_mock,
        },
    ):
        out = macpackage.installed("/path/to/file.pkg")
        installed_mock.assert_called_once_with()
        get_pkg_id_mock.assert_called_once_with("/path/to/file.pkg")
        install_mock.assert_called_once_with(
            "/path/to/file.pkg", "LocalSystem", False, False
        )
        assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_pkg_exists():
    """
    Test installing a PKG file where it's already installed
    """
    expected = {
        "changes": {},
        "comment": "",
        "name": "/path/to/file.pkg",
        "result": True,
    }

    installed_mock = MagicMock(return_value=["com.apple.id", "some.other.id"])
    get_pkg_id_mock = MagicMock(return_value=["some.other.id"])
    install_mock = MagicMock(return_value={"retcode": 0})

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.installed_pkgs": installed_mock,
            "macpackage.get_pkg_id": get_pkg_id_mock,
            "macpackage.install": install_mock,
        },
    ):
        out = macpackage.installed("/path/to/file.pkg")
        installed_mock.assert_called_once_with()
        get_pkg_id_mock.assert_called_once_with("/path/to/file.pkg")
        assert not install_mock.called
        assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_pkg_version_succeeds():
    """
    Test installing a PKG file where the version number matches the current installed version
    """
    expected = {
        "changes": {},
        "comment": "Version already matches .*5\\.1\\.[0-9]",
        "name": "/path/to/file.pkg",
        "result": True,
    }

    installed_mock = MagicMock(return_value=["com.apple.id", "some.other.id"])
    get_pkg_id_mock = MagicMock(return_value=["some.other.id"])
    install_mock = MagicMock(return_value={"retcode": 0})
    cmd_mock = MagicMock(return_value="Version of this: 5.1.9")

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.installed_pkgs": installed_mock,
            "macpackage.get_pkg_id": get_pkg_id_mock,
            "macpackage.install": install_mock,
            "cmd.run": cmd_mock,
        },
    ):
        out = macpackage.installed(
            "/path/to/file.pkg",
            version_check=r"/usr/bin/runme --version=.*5\.1\.[0-9]",
        )
        cmd_mock.assert_called_once_with(
            "/usr/bin/runme --version", output_loglevel="quiet", ignore_retcode=True
        )
        assert not installed_mock.called
        assert not get_pkg_id_mock.called
        assert not install_mock.called
        assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_pkg_version_fails():
    """
    Test installing a PKG file where the version number if different from the expected one
    """
    expected = {
        "changes": {"installed": ["some.other.id"]},
        "comment": (
            "Version Version of this: 1.8.9 doesn't match .*5\\.1\\.[0-9]."
            " /path/to/file.pkg installed"
        ),
        "name": "/path/to/file.pkg",
        "result": True,
    }

    installed_mock = MagicMock(return_value=["com.apple.id"])
    get_pkg_id_mock = MagicMock(return_value=["some.other.id"])
    install_mock = MagicMock(return_value={"retcode": 0})
    cmd_mock = MagicMock(return_value="Version of this: 1.8.9")

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.installed_pkgs": installed_mock,
            "macpackage.get_pkg_id": get_pkg_id_mock,
            "macpackage.install": install_mock,
            "cmd.run": cmd_mock,
        },
    ):
        out = macpackage.installed(
            "/path/to/file.pkg",
            version_check=r"/usr/bin/runme --version=.*5\.1\.[0-9]",
        )
        cmd_mock.assert_called_once_with(
            "/usr/bin/runme --version", output_loglevel="quiet", ignore_retcode=True
        )
        installed_mock.assert_called_once_with()
        get_pkg_id_mock.assert_called_once_with("/path/to/file.pkg")
        install_mock.assert_called_once_with(
            "/path/to/file.pkg", "LocalSystem", False, False
        )
        assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_dmg():
    """
    Test installing a DMG file
    """
    expected = {
        "changes": {"installed": ["some.other.id"]},
        "comment": "/path/to/file.dmg installed",
        "name": "/path/to/file.dmg",
        "result": True,
    }

    mount_mock = MagicMock(return_value=["success", "/tmp/dmg-X"])
    unmount_mock = MagicMock()
    installed_mock = MagicMock(return_value=["com.apple.id"])
    get_pkg_id_mock = MagicMock(return_value=["some.other.id"])
    install_mock = MagicMock(return_value={"retcode": 0})

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.mount": mount_mock,
            "macpackage.unmount": unmount_mock,
            "macpackage.installed_pkgs": installed_mock,
            "macpackage.get_pkg_id": get_pkg_id_mock,
            "macpackage.install": install_mock,
        },
    ):
        out = macpackage.installed("/path/to/file.dmg", dmg=True)
        mount_mock.assert_called_once_with("/path/to/file.dmg")
        unmount_mock.assert_called_once_with("/tmp/dmg-X")
        installed_mock.assert_called_once_with()
        get_pkg_id_mock.assert_called_once_with("/tmp/dmg-X/*.pkg")
        install_mock.assert_called_once_with(
            "/tmp/dmg-X/*.pkg", "LocalSystem", False, False
        )
        assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_dmg_exists():
    """
    Test installing a DMG file when the package already exists
    """
    expected = {
        "changes": {},
        "comment": "",
        "name": "/path/to/file.dmg",
        "result": True,
    }

    mount_mock = MagicMock(return_value=["success", "/tmp/dmg-X"])
    unmount_mock = MagicMock()
    installed_mock = MagicMock(return_value=["com.apple.id", "some.other.id"])
    get_pkg_id_mock = MagicMock(return_value=["some.other.id"])
    install_mock = MagicMock(return_value={"retcode": 0})

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.mount": mount_mock,
            "macpackage.unmount": unmount_mock,
            "macpackage.installed_pkgs": installed_mock,
            "macpackage.get_pkg_id": get_pkg_id_mock,
            "macpackage.install": install_mock,
        },
    ):
        out = macpackage.installed("/path/to/file.dmg", dmg=True)
        mount_mock.assert_called_once_with("/path/to/file.dmg")
        unmount_mock.assert_called_once_with("/tmp/dmg-X")
        installed_mock.assert_called_once_with()
        get_pkg_id_mock.assert_called_once_with("/tmp/dmg-X/*.pkg")
        assert not install_mock.called
        assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_app():
    """
    Test installing an APP file
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {"installed": ["file.app"]},
            "comment": "file.app installed",
            "name": "/path/to/file.app",
            "result": True,
        }

        install_mock = MagicMock()
        exists_mock.return_value = False

        with patch.dict(macpackage.__salt__, {"macpackage.install_app": install_mock}):
            out = macpackage.installed("/path/to/file.app", app=True)

            install_mock.assert_called_once_with("/path/to/file.app", "/Applications/")
            assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_app_exists():
    """
    Test installing an APP file that already exists
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {},
            "comment": "",
            "name": "/path/to/file.app",
            "result": True,
        }

        install_mock = MagicMock()
        exists_mock.return_value = True

        with patch.dict(macpackage.__salt__, {"macpackage.install_app": install_mock}):
            out = macpackage.installed("/path/to/file.app", app=True)

            assert not install_mock.called
            assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_app_dmg():
    """
    Test installing an APP file contained in a DMG file
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {"installed": ["file.app"]},
            "comment": "file.app installed",
            "name": "/path/to/file.dmg",
            "result": True,
        }

        install_mock = MagicMock()
        mount_mock = MagicMock(return_value=["success", "/tmp/dmg-X"])
        unmount_mock = MagicMock()
        cmd_mock = MagicMock(return_value="file.app")
        exists_mock.return_value = False

        with patch.dict(
            macpackage.__salt__,
            {
                "macpackage.install_app": install_mock,
                "macpackage.mount": mount_mock,
                "macpackage.unmount": unmount_mock,
                "cmd.run": cmd_mock,
            },
        ):
            out = macpackage.installed("/path/to/file.dmg", app=True, dmg=True)

            mount_mock.assert_called_once_with("/path/to/file.dmg")
            unmount_mock.assert_called_once_with("/tmp/dmg-X")
            cmd_mock.assert_called_once_with(
                "ls -d *.app", python_shell=True, cwd="/tmp/dmg-X"
            )
            install_mock.assert_called_once_with(
                "/tmp/dmg-X/file.app", "/Applications/"
            )
            assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_app_dmg_exists():
    """
    Test installing an APP file contained in a DMG file where the file exists
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {},
            "comment": "",
            "name": "/path/to/file.dmg",
            "result": True,
        }

        install_mock = MagicMock()
        mount_mock = MagicMock(return_value=["success", "/tmp/dmg-X"])
        unmount_mock = MagicMock()
        cmd_mock = MagicMock(return_value="file.app")
        exists_mock.return_value = True

        with patch.dict(
            macpackage.__salt__,
            {
                "macpackage.install_app": install_mock,
                "macpackage.mount": mount_mock,
                "macpackage.unmount": unmount_mock,
                "cmd.run": cmd_mock,
            },
        ):
            out = macpackage.installed("/path/to/file.dmg", app=True, dmg=True)

            mount_mock.assert_called_once_with("/path/to/file.dmg")
            unmount_mock.assert_called_once_with("/tmp/dmg-X")
            cmd_mock.assert_called_once_with(
                "ls -d *.app", python_shell=True, cwd="/tmp/dmg-X"
            )
            assert not install_mock.called
            assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_installed_pkg_only_if_pass():
    """
    Test installing a PKG file where the only if call passes
    """
    expected = {
        "changes": {"installed": ["some.other.id"]},
        "comment": "/path/to/file.pkg installed",
        "name": "/path/to/file.pkg",
        "result": True,
    }

    installed_mock = MagicMock(return_value=["com.apple.id"])
    get_pkg_id_mock = MagicMock(return_value=["some.other.id"])
    install_mock = MagicMock(return_value={"retcode": 0})
    cmd_mock = MagicMock(return_value=0)

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.installed_pkgs": installed_mock,
            "macpackage.get_pkg_id": get_pkg_id_mock,
            "macpackage.install": install_mock,
            "cmd.retcode": cmd_mock,
        },
    ):
        out = macpackage.installed("/path/to/file.pkg")
        installed_mock.assert_called_once_with()
        get_pkg_id_mock.assert_called_once_with("/path/to/file.pkg")
        install_mock.assert_called_once_with(
            "/path/to/file.pkg", "LocalSystem", False, False
        )
        assert out == expected
