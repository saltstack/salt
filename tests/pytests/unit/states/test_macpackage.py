import pytest

import salt.states.macpackage as macpackage
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {macpackage: {"__opts__": {"test": False}}}


@pytest.fixture
def dry_run_functions():
    functions = {
        "macpackage.installed_pkgs": MagicMock(return_value=[]),
        "macpackage.get_pkg_id": MagicMock(return_value=["pkg.id"]),
        "macpackage.get_mpkg_ids": MagicMock(return_value=["pkg.id"]),
        "macpackage.install": MagicMock(return_value={"retcode": 0}),
        "macpackage.install_app": MagicMock(return_value=""),
        "macpackage.mount": MagicMock(return_value=("success", "/tmp/dmg-X")),
        "macpackage.unmount": MagicMock(return_value={"retcode": 0}),
        "cmd.run": MagicMock(return_value="1.0"),
    }
    with patch.dict(macpackage.__opts__, {"test": True}), patch.dict(
        macpackage.__salt__, functions
    ):
        with patch("shutil.rmtree") as rmtree:
            functions["rmtree"] = rmtree
            yield functions


@pytest.mark.skip_on_windows(reason="Not a Windows test")
@pytest.mark.parametrize("package_type", ["pkg", "mpkg", "app"])
@pytest.mark.parametrize("dmg", [False, True])
@pytest.mark.parametrize(
    "already_installed,force", [(False, False), (True, False), (True, True)]
)
def test_installed_test_mode(
    dry_run_functions, package_type, dmg, already_installed, force
):
    name = f"/path/to/file.{'dmg' if dmg else package_type}"
    dry_run_functions["macpackage.installed_pkgs"].return_value = (
        ["pkg.id"] if already_installed else []
    )
    dry_run_functions["cmd.run"].return_value = "file.app"
    with patch("os.path.exists", return_value=already_installed):
        ret = macpackage.installed(
            name,
            dmg=dmg,
            app=package_type == "app",
            mpkg=package_type == "mpkg",
            force=force,
        )

    if already_installed and not force:
        assert ret["result"] is True
        assert ret["changes"] == {}
    else:
        assert ret["result"] is None
        assert "would be installed" in ret["comment"]
        assert ret["changes"] == {
            "installed": ["file.app" if package_type == "app" else "pkg.id"]
        }
    dry_run_functions["macpackage.install"].assert_not_called()
    dry_run_functions["macpackage.install_app"].assert_not_called()
    if dmg:
        dry_run_functions["macpackage.mount"].assert_called_once_with(name)
        dry_run_functions["macpackage.unmount"].assert_called_once_with(
            "/tmp/dmg-X", return_status=True
        )
        dry_run_functions["rmtree"].assert_called_once_with("/tmp/dmg-X")
    else:
        dry_run_functions["macpackage.mount"].assert_not_called()
        dry_run_functions["macpackage.unmount"].assert_not_called()


@pytest.mark.skip_on_windows(reason="Not a Windows test")
@pytest.mark.parametrize("package_type", ["pkg", "mpkg", "app"])
@pytest.mark.parametrize("dmg", [False, True])
@pytest.mark.parametrize("matches", [True, False])
def test_installed_test_mode_version_check(
    dry_run_functions, package_type, dmg, matches
):
    def run(command, **kwargs):
        if command == "example --version":
            return "1.0" if matches else "0.9"
        assert command == "ls -d *.app"
        return "file.app"

    dry_run_functions["cmd.run"].side_effect = run
    ret = macpackage.installed(
        f"/path/to/file.{'dmg' if dmg else package_type}",
        dmg=dmg,
        app=package_type == "app",
        mpkg=package_type == "mpkg",
        version_check=r"example --version=1\.0",
    )
    assert ret["result"] is (True if matches else None)
    if matches:
        assert ret["changes"] == {}
        assert "Version already matches" in ret["comment"]
    else:
        assert ret["changes"] == {
            "installed": ["file.app" if package_type == "app" else "pkg.id"]
        }
    dry_run_functions["macpackage.install"].assert_not_called()
    dry_run_functions["macpackage.install_app"].assert_not_called()
    if dmg and not matches:
        dry_run_functions["macpackage.unmount"].assert_called_once_with(
            "/tmp/dmg-X", return_status=True
        )
        dry_run_functions["rmtree"].assert_called_once_with("/tmp/dmg-X")
    else:
        dry_run_functions["macpackage.mount"].assert_not_called()
        dry_run_functions["macpackage.unmount"].assert_not_called()


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_dmg_test_mode_inspection_error_cleans_up(dry_run_functions):
    dry_run_functions["macpackage.get_pkg_id"].side_effect = RuntimeError(
        "bad metadata"
    )
    with pytest.raises(RuntimeError, match="bad metadata"):
        macpackage.installed("/path/to/file.dmg", dmg=True)
    dry_run_functions["macpackage.unmount"].assert_called_once_with(
        "/tmp/dmg-X", return_status=True
    )
    dry_run_functions["rmtree"].assert_called_once_with("/tmp/dmg-X")
    dry_run_functions["macpackage.install"].assert_not_called()


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_dmg_test_mode_unmount_failure(dry_run_functions):
    dry_run_functions["macpackage.unmount"].return_value = {"retcode": 1}
    ret = macpackage.installed("/path/to/file.dmg", dmg=True)
    assert ret["result"] is False
    assert "Failed to unmount" in ret["comment"]
    dry_run_functions["rmtree"].assert_not_called()
    dry_run_functions["macpackage.install"].assert_not_called()


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
        with patch("shutil.rmtree", MagicMock()):
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
        with patch("shutil.rmtree", MagicMock()):
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
        with patch("shutil.rmtree", MagicMock()):
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
        with patch("shutil.rmtree", MagicMock()):
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
    unmount_mock = MagicMock(return_value={"retcode": 0})
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
        with patch("shutil.rmtree", MagicMock()):
            out = macpackage.installed("/path/to/file.dmg", dmg=True)
    mount_mock.assert_called_once_with("/path/to/file.dmg")
    unmount_mock.assert_called_once_with("/tmp/dmg-X", return_status=True)
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
    unmount_mock = MagicMock(return_value={"retcode": 0})
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
        with patch("shutil.rmtree", MagicMock()):
            out = macpackage.installed("/path/to/file.dmg", dmg=True)
    mount_mock.assert_called_once_with("/path/to/file.dmg")
    unmount_mock.assert_called_once_with("/tmp/dmg-X", return_status=True)
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
            with patch("shutil.rmtree", MagicMock()):
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
            with patch("shutil.rmtree", MagicMock()):
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
        unmount_mock = MagicMock(return_value={"retcode": 0})
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
            with patch("shutil.rmtree", MagicMock()):
                out = macpackage.installed("/path/to/file.dmg", app=True, dmg=True)

        mount_mock.assert_called_once_with("/path/to/file.dmg")
        unmount_mock.assert_called_once_with("/tmp/dmg-X", return_status=True)
        cmd_mock.assert_called_once_with(
            "ls -d *.app", python_shell=True, cwd="/tmp/dmg-X"
        )
        install_mock.assert_called_once_with("/tmp/dmg-X/file.app", "/Applications/")
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
        unmount_mock = MagicMock(return_value={"retcode": 0})
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
            with patch("shutil.rmtree", MagicMock()):
                out = macpackage.installed("/path/to/file.dmg", app=True, dmg=True)

        mount_mock.assert_called_once_with("/path/to/file.dmg")
        unmount_mock.assert_called_once_with("/tmp/dmg-X", return_status=True)
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
        with patch("shutil.rmtree", MagicMock()):
            out = macpackage.installed("/path/to/file.pkg")
    installed_mock.assert_called_once_with()
    get_pkg_id_mock.assert_called_once_with("/path/to/file.pkg")
    install_mock.assert_called_once_with(
        "/path/to/file.pkg", "LocalSystem", False, False
    )
    assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_unmounted_dir_cleans_up():
    """
    Test an unmounted volume removes the mount dir.
    """
    expected = {
        "changes": {"installed": ["some.other.id"]},
        "comment": "/path/to/file.dmg installed",
        "name": "/path/to/file.dmg",
        "result": True,
    }
    rmtree_mock = MagicMock()

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.mount": MagicMock(return_value=["success", "/tmp/dmg-X"]),
            "macpackage.unmount": MagicMock(return_value={"retcode": 0}),
            "macpackage.installed_pkgs": MagicMock(return_value=["com.apple.id"]),
            "macpackage.get_pkg_id": MagicMock(return_value=["some.other.id"]),
            "macpackage.install": MagicMock(return_value={"retcode": 0}),
        },
    ):
        with patch("shutil.rmtree", rmtree_mock):
            out = macpackage.installed("/path/to/file.dmg", dmg=True)
    rmtree_mock.assert_called_once_with("/tmp/dmg-X")
    assert out == expected


@pytest.mark.skip_on_windows(reason="Not a Windows test")
def test_failed_unmount_leaves_dir():
    """
    Test a mounted volume that fails to unmount does not attempt to remove the mount dir.
    """
    expected = {
        "changes": {"installed": ["some.other.id"]},
        "comment": "/path/to/file.dmg installed",
        "name": "/path/to/file.dmg",
        "result": True,
    }
    rmtree_mock = MagicMock()

    with patch.dict(
        macpackage.__salt__,
        {
            "macpackage.mount": MagicMock(return_value=["success", "/tmp/dmg-X"]),
            "macpackage.unmount": MagicMock(return_value={"retcode": 1}),
            "macpackage.installed_pkgs": MagicMock(return_value=["com.apple.id"]),
            "macpackage.get_pkg_id": MagicMock(return_value=["some.other.id"]),
            "macpackage.install": MagicMock(return_value={"retcode": 0}),
        },
    ):
        with patch("shutil.rmtree", rmtree_mock):
            macpackage.installed("/path/to/file.dmg", dmg=True)
    rmtree_mock.assert_not_called()
