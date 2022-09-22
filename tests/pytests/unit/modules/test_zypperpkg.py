"""
    :codeauthor: Gareth J. Greenaway <ggreenaway@vmware.com>
"""


import os

import pytest

import salt.modules.pkg_resource as pkg_resource
import salt.modules.zypperpkg as zypper
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {zypper: {"rpm": None}, pkg_resource: {}}


def test_list_pkgs_no_context():
    """
    Test packages listing.

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    rpm_out = [
        "protobuf-java_|-(none)_|-2.6.1_|-3.1.develHead_|-noarch_|-(none)_|-1499257756",
        "yast2-ftp-server_|-(none)_|-3.1.8_|-8.1_|-x86_64_|-(none)_|-1499257798",
        "jose4j_|-(none)_|-0.4.4_|-2.1.develHead_|-noarch_|-(none)_|-1499257756",
        "apache-commons-cli_|-(none)_|-1.2_|-1.233_|-noarch_|-(none)_|-1498636510",
        "jakarta-commons-discovery_|-(none)_|-0.4_|-129.686_|-noarch_|-(none)_|-1498636511",
        "susemanager-build-keys-web_|-(none)_|-12.0_|-5.1.develHead_|-noarch_|-(none)_|-1498636510",
        "gpg-pubkey_|-(none)_|-39db7c82_|-5847eb1f_|-(none)_|-(none)_|-1519203802",
        "gpg-pubkey_|-(none)_|-8a7c64f9_|-5aaa93ca_|-(none)_|-(none)_|-1529925595",
        "kernel-default_|-(none)_|-4.4.138_|-94.39.1_|-x86_64_|-(none)_|-1529936067",
        "kernel-default_|-(none)_|-4.4.73_|-5.1_|-x86_64_|-(none)_|-1503572639",
        "perseus-dummy_|-(none)_|-1.1_|-1.1_|-i586_|-(none)_|-1529936062",
    ]
    with patch.dict(zypper.__grains__, {"osarch": "x86_64"}), patch.dict(
        zypper.__salt__,
        {"cmd.run": MagicMock(return_value=os.linesep.join(rpm_out))},
    ), patch.dict(zypper.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        zypper.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        zypper.__salt__, {"pkg_resource.stringify": MagicMock()}
    ), patch.object(
        zypper, "_list_pkgs_from_context"
    ) as list_pkgs_context_mock:
        pkgs = zypper.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        pkgs = zypper.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()


def test_normalize_name():
    """
    Test that package is normalized only when it should be
    """
    with patch.dict(zypper.__grains__, {"osarch": "x86_64"}):
        result = zypper.normalize_name("foo")
        assert result == "foo", result
        result = zypper.normalize_name("foo.x86_64")
        assert result == "foo", result
        result = zypper.normalize_name("foo.noarch")
        assert result == "foo", result

    with patch.dict(zypper.__grains__, {"osarch": "aarch64"}):
        result = zypper.normalize_name("foo")
        assert result == "foo", result
        result = zypper.normalize_name("foo.aarch64")
        assert result == "foo", result
        result = zypper.normalize_name("foo.noarch")
        assert result == "foo", result


def test_pkg_hold():
    """
    Tests holding packages with Zypper
    """

    # Test openSUSE 15.3
    list_locks_mock = {
        "bar": {"type": "package", "match_type": "glob", "case_sensitive": "on"},
        "minimal_base": {
            "type": "pattern",
            "match_type": "glob",
            "case_sensitive": "on",
        },
        "baz": {"type": "package", "match_type": "glob", "case_sensitive": "on"},
    }

    cmd = MagicMock(
        return_value={
            "pid": 1234,
            "retcode": 0,
            "stdout": "Specified lock has been successfully added.",
            "stderr": "",
        }
    )
    with patch.object(
        zypper, "list_locks", MagicMock(return_value=list_locks_mock)
    ), patch.dict(zypper.__salt__, {"cmd.run_all": cmd}):
        ret = zypper.hold("foo")
        assert ret["foo"]["changes"]["old"] == ""
        assert ret["foo"]["changes"]["new"] == "hold"
        assert ret["foo"]["comment"] == "Package foo is now being held."
        cmd.assert_called_once_with(
            ["zypper", "--non-interactive", "--no-refresh", "al", "foo"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )
        cmd.reset_mock()
        ret = zypper.hold(pkgs=["foo", "bar"])
        assert ret["foo"]["changes"]["old"] == ""
        assert ret["foo"]["changes"]["new"] == "hold"
        assert ret["foo"]["comment"] == "Package foo is now being held."
        assert ret["bar"]["changes"] == {}
        assert ret["bar"]["comment"] == "Package bar is already set to be held."
        cmd.assert_called_once_with(
            ["zypper", "--non-interactive", "--no-refresh", "al", "foo"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


def test_pkg_unhold():
    """
    Tests unholding packages with Zypper
    """

    # Test openSUSE 15.3
    list_locks_mock = {
        "bar": {"type": "package", "match_type": "glob", "case_sensitive": "on"},
        "minimal_base": {
            "type": "pattern",
            "match_type": "glob",
            "case_sensitive": "on",
        },
        "baz": {"type": "package", "match_type": "glob", "case_sensitive": "on"},
    }

    cmd = MagicMock(
        return_value={
            "pid": 1234,
            "retcode": 0,
            "stdout": "1 lock has been successfully removed.",
            "stderr": "",
        }
    )
    with patch.object(
        zypper, "list_locks", MagicMock(return_value=list_locks_mock)
    ), patch.dict(zypper.__salt__, {"cmd.run_all": cmd}):
        ret = zypper.unhold("foo")
        assert ret["foo"]["comment"] == "Package foo was already unheld."
        cmd.assert_not_called()
        cmd.reset_mock()
        ret = zypper.unhold(pkgs=["foo", "bar"])
        assert ret["foo"]["changes"] == {}
        assert ret["foo"]["comment"] == "Package foo was already unheld."
        assert ret["bar"]["changes"]["old"] == "hold"
        assert ret["bar"]["changes"]["new"] == ""
        assert ret["bar"]["comment"] == "Package bar is no longer held."
        cmd.assert_called_once_with(
            ["zypper", "--non-interactive", "--no-refresh", "rl", "bar"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


def test_pkg_list_holds():
    """
    Tests listing of calculated held packages with Zypper
    """

    # Test openSUSE 15.3
    list_locks_mock = {
        "bar": {"type": "package", "match_type": "glob", "case_sensitive": "on"},
        "minimal_base": {
            "type": "pattern",
            "match_type": "glob",
            "case_sensitive": "on",
        },
        "baz": {"type": "package", "match_type": "glob", "case_sensitive": "on"},
    }
    installed_pkgs = {
        "foo": [{"edition": "1.2.3-1.1"}],
        "bar": [{"edition": "2.3.4-2.1", "epoch": "2"}],
    }

    def zypper_search_mock(name, *_args, **_kwargs):
        if name in installed_pkgs:
            return {name: installed_pkgs.get(name)}

    with patch.object(
        zypper, "list_locks", MagicMock(return_value=list_locks_mock)
    ), patch.object(
        zypper, "search", MagicMock(side_effect=zypper_search_mock)
    ), patch.object(
        zypper, "info_installed", MagicMock(side_effect=zypper_search_mock)
    ):
        ret = zypper.list_holds()
        assert len(ret) == 1
        assert "bar-2:2.3.4-2.1.*" in ret
