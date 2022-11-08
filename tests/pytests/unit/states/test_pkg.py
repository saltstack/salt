import logging

import pytest

import salt.modules.beacons as beaconmod
import salt.modules.pkg_resource as pkg_resource
import salt.modules.yumpkg as yumpkg
import salt.states.beacon as beaconstate
import salt.states.pkg as pkg
import salt.utils.state as state_utils
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        pkg: {
            "__env__": "base",
            "__salt__": {},
            "__grains__": {"os": "CentOS", "os_family": "RedHat"},
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {"state.gen_tag": state_utils.gen_tag},
        },
        beaconstate: {"__salt__": {}, "__opts__": {}},
        beaconmod: {"__salt__": {}, "__opts__": {}},
        pkg_resource: {
            "__salt__": {},
            "__grains__": {"os": "CentOS", "os_family": "RedHat"},
        },
        yumpkg: {
            "__salt__": {},
            "__grains__": {"osarch": "x86_64", "osmajorrelease": 7},
            "__opts__": {},
        },
    }


@pytest.fixture(scope="module")
def pkgs():
    return {
        "pkga": {"old": "1.0.1", "new": "2.0.1"},
        "pkgb": {"old": "1.0.2", "new": "2.0.2"},
        "pkgc": {"old": "1.0.3", "new": "2.0.3"},
    }


@pytest.fixture(scope="module")
def list_pkgs():
    return {
        "pkga": "1.0.1",
        "pkgb": "1.0.2",
        "pkgc": "1.0.3",
    }


def test_uptodate_with_changes(pkgs):
    """
    Test pkg.uptodate with simulated changes
    """

    list_upgrades = MagicMock(
        return_value={pkgname: pkgver["new"] for pkgname, pkgver in pkgs.items()}
    )
    upgrade = MagicMock(return_value=pkgs)
    version = MagicMock(side_effect=lambda pkgname, **_: pkgs[pkgname]["old"])

    with patch.dict(
        pkg.__salt__,
        {
            "pkg.list_upgrades": list_upgrades,
            "pkg.upgrade": upgrade,
            "pkg.version": version,
        },
    ):

        # Run state with test=false
        with patch.dict(pkg.__opts__, {"test": False}):
            ret = pkg.uptodate("dummy", test=True)
            assert ret["result"]
            assert ret["changes"] == pkgs

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate("dummy", test=True)
            assert ret["result"] is None
            assert ret["changes"] == pkgs


def test_uptodate_with_pkgs_with_changes(pkgs):
    """
    Test pkg.uptodate with simulated changes
    """

    list_upgrades = MagicMock(
        return_value={pkgname: pkgver["new"] for pkgname, pkgver in pkgs.items()}
    )
    upgrade = MagicMock(return_value=pkgs)
    version = MagicMock(side_effect=lambda pkgname, **_: pkgs[pkgname]["old"])

    with patch.dict(
        pkg.__salt__,
        {
            "pkg.list_upgrades": list_upgrades,
            "pkg.upgrade": upgrade,
            "pkg.version": version,
        },
    ):
        # Run state with test=false
        with patch.dict(pkg.__opts__, {"test": False}):
            ret = pkg.uptodate(
                "dummy",
                test=True,
                pkgs=[pkgname for pkgname in pkgs],
            )
            assert ret["result"]
            assert ret["changes"] == pkgs

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate(
                "dummy",
                test=True,
                pkgs=[pkgname for pkgname in pkgs],
            )
            assert ret["result"] is None
            assert ret["changes"] == pkgs


def test_uptodate_no_changes():
    """
    Test pkg.uptodate with no changes
    """
    list_upgrades = MagicMock(return_value={})
    upgrade = MagicMock(return_value={})

    with patch.dict(
        pkg.__salt__, {"pkg.list_upgrades": list_upgrades, "pkg.upgrade": upgrade}
    ):

        # Run state with test=false
        with patch.dict(pkg.__opts__, {"test": False}):

            ret = pkg.uptodate("dummy", test=True)
            assert ret["result"]
            assert ret["changes"] == {}

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate("dummy", test=True)
            assert ret["result"]
            assert ret["changes"] == {}


def test_uptodate_with_pkgs_no_changes(pkgs):
    """
    Test pkg.uptodate with no changes
    """

    list_upgrades = MagicMock(return_value={})
    upgrade = MagicMock(return_value={})

    with patch.dict(
        pkg.__salt__, {"pkg.list_upgrades": list_upgrades, "pkg.upgrade": upgrade}
    ):
        # Run state with test=false
        with patch.dict(pkg.__opts__, {"test": False}):
            ret = pkg.uptodate(
                "dummy",
                test=True,
                pkgs=[pkgname for pkgname in pkgs],
            )
            assert ret["result"]
            assert ret["changes"] == {}

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate(
                "dummy",
                test=True,
                pkgs=[pkgname for pkgname in pkgs],
            )
            assert ret["result"]
            assert ret["changes"] == {}


def test_uptodate_with_failed_changes(pkgs):
    """
    Test pkg.uptodate with simulated failed changes
    """

    list_upgrades = MagicMock(
        return_value={pkgname: pkgver["new"] for pkgname, pkgver in pkgs.items()}
    )
    upgrade = MagicMock(return_value={})
    version = MagicMock(side_effect=lambda pkgname, **_: pkgs[pkgname]["old"])

    with patch.dict(
        pkg.__salt__,
        {
            "pkg.list_upgrades": list_upgrades,
            "pkg.upgrade": upgrade,
            "pkg.version": version,
        },
    ):
        # Run state with test=false
        with patch.dict(pkg.__opts__, {"test": False}):
            ret = pkg.uptodate(
                "dummy",
                test=True,
                pkgs=[pkgname for pkgname in pkgs],
            )
            assert not ret["result"]
            assert ret["changes"] == {}

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate(
                "dummy",
                test=True,
                pkgs=[pkgname for pkgname in pkgs],
            )
            assert ret["result"] is None
            assert ret["changes"] == pkgs


@pytest.mark.parametrize(
    "version_string, expected_version_conditions",
    [
        (
            "> 1.0.0, < 15.0.0, != 14.0.1",
            [(">", "1.0.0"), ("<", "15.0.0"), ("!=", "14.0.1")],
        ),
        (
            "> 1.0.0,< 15.0.0,!= 14.0.1",
            [(">", "1.0.0"), ("<", "15.0.0"), ("!=", "14.0.1")],
        ),
        (">= 1.0.0, < 15.0.0", [(">=", "1.0.0"), ("<", "15.0.0")]),
        (">=1.0.0,< 15.0.0", [(">=", "1.0.0"), ("<", "15.0.0")]),
        ("< 15.0.0", [("<", "15.0.0")]),
        ("<15.0.0", [("<", "15.0.0")]),
        ("15.0.0", [("==", "15.0.0")]),
        ("", []),
    ],
)
def test_parse_version_string(version_string, expected_version_conditions):
    version_conditions = pkg._parse_version_string(version_string)
    assert len(expected_version_conditions) == len(version_conditions)
    for expected_version_condition, version_condition in zip(
        expected_version_conditions, version_conditions
    ):
        assert expected_version_condition[0] == version_condition[0]
        assert expected_version_condition[1] == version_condition[1]


@pytest.mark.parametrize(
    "version_string, installed_versions, expected_result",
    [
        ("> 1.0.0, < 15.0.0, != 14.0.1", [], False),
        ("> 1.0.0, < 15.0.0, != 14.0.1", ["1.0.0"], False),
        ("> 1.0.0, < 15.0.0, != 14.0.1", ["14.0.1"], False),
        ("> 1.0.0, < 15.0.0, != 14.0.1", ["16.0.0"], False),
        ("> 1.0.0, < 15.0.0, != 14.0.1", ["2.0.0"], True),
        (
            "> 1.0.0, < 15.0.0, != 14.0.1",
            ["1.0.0", "14.0.1", "16.0.0", "2.0.0"],
            True,
        ),
        ("> 15.0.0", [], False),
        ("> 15.0.0", ["1.0.0"], False),
        ("> 15.0.0", ["16.0.0"], True),
        ("15.0.0", [], False),
        ("15.0.0", ["15.0.0"], True),
        # No version specified, whatever version installed. This is threated like ANY version installed fulfills.
        ("", ["15.0.0"], True),
        # No version specified, no version installed.
        ("", [], False),
    ],
)
def test_fulfills_version_string(version_string, installed_versions, expected_result):
    msg = "version_string: {}, installed_versions: {}, expected_result: {}".format(
        version_string, installed_versions, expected_result
    )
    assert expected_result == pkg._fulfills_version_string(
        installed_versions, version_string
    )


@pytest.mark.parametrize(
    "installed_versions, operator, version, expected_result",
    [
        (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "==", "1.0.0", True),
        (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], ">=", "1.0.0", True),
        (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], ">", "1.0.0", True),
        (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "<", "2.0.0", True),
        (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "<=", "2.0.0", True),
        (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "!=", "1.0.0", True),
        (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "==", "17.0.0", False),
        (["1.0.0"], "!=", "1.0.0", False),
        ([], "==", "17.0.0", False),
    ],
)
def test_fulfills_version_spec(installed_versions, operator, version, expected_result):
    msg = (
        "installed_versions: {}, operator: {}, version: {}, expected_result: {}".format(
            installed_versions, operator, version, expected_result
        )
    )
    assert expected_result == pkg._fulfills_version_spec(
        installed_versions, operator, version
    )


def test_mod_beacon(tmp_path):
    """
    Test to create a beacon based on a pkg
    """
    name = "vim"

    with patch.dict(pkg.__salt__, {"beacons.list": MagicMock(return_value={})}):
        with patch.dict(pkg.__states__, {"beacon.present": beaconstate.present}):
            ret = pkg.mod_beacon(name, sfun="latest")
            expected = {
                "name": name,
                "changes": {},
                "result": False,
                "comment": (
                    "pkg.latest does not work with the mod_beacon state function"
                ),
            }

            assert ret == expected

            ret = pkg.mod_beacon(name, sfun="installed")
            expected = {
                "name": name,
                "changes": {},
                "result": True,
                "comment": "Not adding beacon.",
            }

            assert ret == expected

    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_available_complete",
            "beacons": ["pkg"],
        },
        {
            "valid": True,
            "tag": "/salt/minion/minion_beacon_validation_complete",
            "vcomment": "Valid beacon configuration",
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_add_complete",
            "beacons": {
                "beacon_pkg_vim": [
                    {"pkgs": [name]},
                    {"interval": 60},
                    {"beacon_module": "pkg"},
                ]
            },
        },
    ]
    mock = MagicMock(return_value=True)
    beacon_state_mocks = {
        "beacons.list": beaconmod.list_,
        "beacons.add": beaconmod.add,
        "beacons.list_available": beaconmod.list_available,
        "event.fire": mock,
    }

    beacon_mod_mocks = {"event.fire": mock}

    sock_dir = str(tmp_path / "test-socks")
    with patch.dict(pkg.__states__, {"beacon.present": beaconstate.present}):
        with patch.dict(beaconstate.__salt__, beacon_state_mocks):
            with patch.dict(beaconmod.__salt__, beacon_mod_mocks):
                with patch.dict(
                    beaconmod.__opts__, {"beacons": {}, "sock_dir": sock_dir}
                ):
                    with patch.object(
                        SaltEvent, "get_event", side_effect=event_returns
                    ):
                        ret = pkg.mod_beacon(name, sfun="installed", beacon=True)
                        expected = {
                            "name": "beacon_pkg_vim",
                            "changes": {},
                            "result": True,
                            "comment": "Adding beacon_pkg_vim to beacons",
                        }

                        assert ret == expected


def test_mod_aggregate():
    """
    Test to mod_aggregate function
    """
    low = {
        "state": "pkg",
        "name": "other_pkgs",
        "pkgs": ["byobu"],
        "aggregate": True,
        "fun": "installed",
    }

    chunks = [
        {
            "state": "file",
            "name": "/tmp/install-vim",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "/tmp/install-vim",
            "order": 10000,
            "fun": "managed",
        },
        {
            "state": "file",
            "name": "/tmp/install-tmux",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "/tmp/install-tmux",
            "order": 10001,
            "fun": "managed",
        },
        {
            "state": "pkg",
            "name": "other_pkgs",
            "__sls__": "47628",
            "__env __": "base",
            "__id__": "other_pkgs",
            "pkgs": ["byobu"],
            "aggregate": True,
            "order": 10002,
            "fun": "installed",
        },
        {
            "state": "pkg",
            "name": "bc",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "bc",
            "hold": True,
            "order": 10003,
            "fun": "installed",
        },
        {
            "state": "pkg",
            "name": "vim",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "vim",
            "require": ["/tmp/install-vim"],
            "order": 10004,
            "fun": "installed",
        },
        {
            "state": "pkg",
            "name": "tmux",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "tmux",
            "require": ["/tmp/install-tmux"],
            "order": 10005,
            "fun": "installed",
        },
        {
            "state": "pkgrepo",
            "name": "deb https://packages.cloud.google.com/apt cloud-sdk main",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "google-cloud-repo",
            "humanname": "Google Cloud SDK",
            "file": "/etc/apt/sources.list.d/google-cloud-sdk.list",
            "key_url": "https://packages.cloud.google.com/apt/doc/apt-key.gpg",
            "order": 10006,
            "fun": "managed",
        },
        {
            "state": "pkg",
            "name": "google-cloud-sdk",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "google-cloud-sdk",
            "require": ["google-cloud-repo"],
            "order": 10007,
            "fun": "installed",
        },
    ]

    running = {
        "file_|-/tmp/install-vim_| -/tmp/install-vim_|-managed": {
            "changes": {},
            "comment": "File /tmp/install-vim exists with proper permissions. No changes made.",
            "name": "/tmp/install-vim",
            "result": True,
            "__sls__": "47628",
            "__run_num__": 0,
            "start_time": "18:41:20.987275",
            "duration": 5.833,
            "__id__": "/tmp/install-vim",
        },
        "file_|-/tmp/install-tmux_|-/tmp/install-tmux_|-managed": {
            "changes": {},
            "comment": "File /tmp/install-tmux exists with proper permissions. No changes made.",
            "name": "/tmp/install-tmux",
            "result": True,
            "__sls__": "47628",
            "__run_num__": 1,
            "start_time": "18:41:20.993258",
            "duration": 1.263,
            "__id__": "/tmp/install-tmux",
        },
    }

    expected = {
        "pkgs": ["byobu", "byobu", "vim", "tmux", "google-cloud-sdk"],
        "name": "other_pkgs",
        "fun": "installed",
        "aggregate": True,
        "state": "pkg",
    }
    res = pkg.mod_aggregate(low, chunks, running)
    assert res == expected


def test_installed_with_changes_test_true(list_pkgs):
    """
    Test pkg.installed with simulated changes
    """

    list_pkgs = MagicMock(return_value=list_pkgs)

    with patch.dict(
        pkg.__salt__,
        {
            "pkg.list_pkgs": list_pkgs,
        },
    ):

        expected = {"dummy": {"new": "installed", "old": ""}}
        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.installed("dummy", test=True)
            assert ret["result"] is None
            assert ret["changes"] == expected


@pytest.mark.parametrize("action", ["removed", "purged"])
def test_removed_purged_with_changes_test_true(list_pkgs, action):
    """
    Test pkg.removed with simulated changes
    """

    list_pkgs = MagicMock(return_value=list_pkgs)

    mock_parse_targets = MagicMock(return_value=[{"pkga": None}, "repository"])

    with patch.dict(
        pkg.__salt__,
        {
            "pkg.list_pkgs": list_pkgs,
            "pkg_resource.parse_targets": mock_parse_targets,
            "pkg_resource.version_clean": MagicMock(return_value=None),
        },
    ):

        expected = {"pkga": {"new": "{}".format(action), "old": ""}}
        pkg_actions = {"removed": pkg.removed, "purged": pkg.purged}

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg_actions[action]("pkga", test=True)
            assert ret["result"] is None
            assert ret["changes"] == expected


@pytest.mark.parametrize(
    "package_manager",
    [("Zypper"), ("YUM/DNF"), ("APT")],
)
def test_held_unheld(package_manager):
    """
    Test pkg.held and pkg.unheld with Zypper, YUM/DNF and APT
    """

    if package_manager == "Zypper":
        list_holds_func = "pkg.list_locks"
        list_holds_mock = MagicMock(
            return_value={
                "bar": {
                    "type": "package",
                    "match_type": "glob",
                    "case_sensitive": "on",
                },
                "minimal_base": {
                    "type": "pattern",
                    "match_type": "glob",
                    "case_sensitive": "on",
                },
                "baz": {
                    "type": "package",
                    "match_type": "glob",
                    "case_sensitive": "on",
                },
            }
        )
    elif package_manager == "YUM/DNF":
        list_holds_func = "pkg.list_holds"
        list_holds_mock = MagicMock(
            return_value=[
                "bar-0:1.2.3-1.1.*",
                "baz-0:2.3.4-2.1.*",
            ]
        )
    elif package_manager == "APT":
        list_holds_func = "pkg.get_selections"
        list_holds_mock = MagicMock(
            return_value={
                "hold": [
                    "bar",
                    "baz",
                ]
            }
        )

    def pkg_hold(name, pkgs=None, *_args, **__kwargs):
        if name and pkgs is None:
            pkgs = [name]
        ret = {}
        for pkg in pkgs:
            ret.update(
                {
                    pkg: {
                        "name": pkg,
                        "changes": {"new": "hold", "old": ""},
                        "result": True,
                        "comment": "Package {} is now being held.".format(pkg),
                    }
                }
            )
        return ret

    def pkg_unhold(name, pkgs=None, *_args, **__kwargs):
        if name and pkgs is None:
            pkgs = [name]
        ret = {}
        for pkg in pkgs:
            ret.update(
                {
                    pkg: {
                        "name": pkg,
                        "changes": {"new": "", "old": "hold"},
                        "result": True,
                        "comment": "Package {} is no longer held.".format(pkg),
                    }
                }
            )
        return ret

    hold_mock = MagicMock(side_effect=pkg_hold)
    unhold_mock = MagicMock(side_effect=pkg_unhold)

    # Testing with Zypper
    with patch.dict(
        pkg.__salt__,
        {
            list_holds_func: list_holds_mock,
            "pkg.hold": hold_mock,
            "pkg.unhold": unhold_mock,
        },
    ):
        # Holding one of two packages
        ret = pkg.held("held-test", pkgs=["foo", "bar"])
        assert "foo" in ret["changes"]
        assert len(ret["changes"]) == 1
        hold_mock.assert_called_once_with(name="held-test", pkgs=["foo"])
        unhold_mock.assert_not_called()

        hold_mock.reset_mock()
        unhold_mock.reset_mock()

        # Holding one of two packages and replacing all the rest held packages
        ret = pkg.held("held-test", pkgs=["foo", "bar"], replace=True)
        assert "foo" in ret["changes"]
        assert "baz" in ret["changes"]
        assert len(ret["changes"]) == 2
        hold_mock.assert_called_once_with(name="held-test", pkgs=["foo"])
        unhold_mock.assert_called_once_with(name="held-test", pkgs=["baz"])

        hold_mock.reset_mock()
        unhold_mock.reset_mock()

        # Remove all holds
        ret = pkg.held("held-test", pkgs=[], replace=True)
        assert "bar" in ret["changes"]
        assert "baz" in ret["changes"]
        assert len(ret["changes"]) == 2
        hold_mock.assert_not_called()
        unhold_mock.assert_any_call(name="held-test", pkgs=["baz"])
        unhold_mock.assert_any_call(name="held-test", pkgs=["bar"])

        hold_mock.reset_mock()
        unhold_mock.reset_mock()

        # Unolding one of two packages
        ret = pkg.unheld("held-test", pkgs=["foo", "bar"])
        assert "bar" in ret["changes"]
        assert len(ret["changes"]) == 1
        unhold_mock.assert_called_once_with(name="held-test", pkgs=["bar"])
        hold_mock.assert_not_called()

        hold_mock.reset_mock()
        unhold_mock.reset_mock()

        # Remove all holds
        ret = pkg.unheld("held-test", all=True)
        assert "bar" in ret["changes"]
        assert "baz" in ret["changes"]
        assert len(ret["changes"]) == 2
        hold_mock.assert_not_called()
        unhold_mock.assert_any_call(name="held-test", pkgs=["baz"])
        unhold_mock.assert_any_call(name="held-test", pkgs=["bar"])


def test_installed_with_single_normalize():
    """
    Test pkg.installed with preventing multiple package name normalisation
    """

    list_no_weird_installed = {
        "pkga": "1.0.1",
        "pkgb": "1.0.2",
        "pkgc": "1.0.3",
    }
    list_no_weird_installed_ver_list = {
        "pkga": ["1.0.1"],
        "pkgb": ["1.0.2"],
        "pkgc": ["1.0.3"],
    }
    list_with_weird_installed = {
        "pkga": "1.0.1",
        "pkgb": "1.0.2",
        "pkgc": "1.0.3",
        "weird-name-1.2.3-1234.5.6.test7tst.x86_64": "20220214-2.1",
    }
    list_with_weird_installed_ver_list = {
        "pkga": ["1.0.1"],
        "pkgb": ["1.0.2"],
        "pkgc": ["1.0.3"],
        "weird-name-1.2.3-1234.5.6.test7tst.x86_64": ["20220214-2.1"],
    }
    list_pkgs = MagicMock(
        side_effect=[
            # For the package with version specified
            list_no_weird_installed_ver_list,
            {},
            list_no_weird_installed,
            list_no_weird_installed_ver_list,
            list_with_weird_installed,
            list_with_weird_installed_ver_list,
            # For the package with no version specified
            list_no_weird_installed_ver_list,
            {},
            list_no_weird_installed,
            list_no_weird_installed_ver_list,
            list_with_weird_installed,
            list_with_weird_installed_ver_list,
        ]
    )

    salt_dict = {
        "pkg.install": yumpkg.install,
        "pkg.list_pkgs": list_pkgs,
        "pkg.normalize_name": yumpkg.normalize_name,
        "pkg_resource.version_clean": pkg_resource.version_clean,
        "pkg_resource.parse_targets": pkg_resource.parse_targets,
    }

    with patch("salt.modules.yumpkg.list_pkgs", list_pkgs), patch(
        "salt.modules.yumpkg.version_cmp", MagicMock(return_value=0)
    ), patch(
        "salt.modules.yumpkg._call_yum", MagicMock(return_value={"retcode": 0})
    ) as call_yum_mock, patch.dict(
        pkg.__salt__, salt_dict
    ), patch.dict(
        pkg_resource.__salt__, salt_dict
    ), patch.dict(
        yumpkg.__salt__, salt_dict
    ), patch.dict(
        yumpkg.__grains__, {"os": "CentOS", "osarch": "x86_64", "osmajorrelease": 7}
    ), patch.object(
        yumpkg, "list_holds", MagicMock()
    ):

        expected = {
            "weird-name-1.2.3-1234.5.6.test7tst.x86_64": {
                "old": "",
                "new": "20220214-2.1",
            }
        }
        ret = pkg.installed(
            "test_install",
            pkgs=[{"weird-name-1.2.3-1234.5.6.test7tst.x86_64.noarch": "20220214-2.1"}],
        )
        call_yum_mock.assert_called_once()
        assert (
            "weird-name-1.2.3-1234.5.6.test7tst.x86_64-20220214-2.1"
            in call_yum_mock.mock_calls[0].args[0]
        )
        assert ret["result"]
        assert ret["changes"] == expected

        call_yum_mock.reset_mock()

        ret = pkg.installed(
            "test_install",
            pkgs=["weird-name-1.2.3-1234.5.6.test7tst.x86_64.noarch"],
        )
        call_yum_mock.assert_called_once()
        assert (
            "weird-name-1.2.3-1234.5.6.test7tst.x86_64"
            in call_yum_mock.mock_calls[0].args[0]
        )
        assert ret["result"]
        assert ret["changes"] == expected


def test_removed_with_single_normalize():
    """
    Test pkg.removed with preventing multiple package name normalisation
    """

    list_no_weird_installed = {
        "pkga": "1.0.1",
        "pkgb": "1.0.2",
        "pkgc": "1.0.3",
    }
    list_no_weird_installed_ver_list = {
        "pkga": ["1.0.1"],
        "pkgb": ["1.0.2"],
        "pkgc": ["1.0.3"],
    }
    list_with_weird_installed = {
        "pkga": "1.0.1",
        "pkgb": "1.0.2",
        "pkgc": "1.0.3",
        "weird-name-1.2.3-1234.5.6.test7tst.x86_64": "20220214-2.1",
    }
    list_with_weird_installed_ver_list = {
        "pkga": ["1.0.1"],
        "pkgb": ["1.0.2"],
        "pkgc": ["1.0.3"],
        "weird-name-1.2.3-1234.5.6.test7tst.x86_64": ["20220214-2.1"],
    }
    list_pkgs = MagicMock(
        side_effect=[
            # For the package with version specified
            list_with_weird_installed_ver_list,
            list_with_weird_installed,
            list_no_weird_installed,
            list_no_weird_installed_ver_list,
            # For the package with no version specified
            list_with_weird_installed_ver_list,
            list_with_weird_installed,
            list_no_weird_installed,
            list_no_weird_installed_ver_list,
        ]
    )

    salt_dict = {
        "pkg.remove": yumpkg.remove,
        "pkg.list_pkgs": list_pkgs,
        "pkg.normalize_name": yumpkg.normalize_name,
        "pkg_resource.parse_targets": pkg_resource.parse_targets,
        "pkg_resource.version_clean": pkg_resource.version_clean,
    }

    with patch("salt.modules.yumpkg.list_pkgs", list_pkgs), patch(
        "salt.modules.yumpkg.version_cmp", MagicMock(return_value=0)
    ), patch(
        "salt.modules.yumpkg._call_yum", MagicMock(return_value={"retcode": 0})
    ) as call_yum_mock, patch.dict(
        pkg.__salt__, salt_dict
    ), patch.dict(
        pkg_resource.__salt__, salt_dict
    ), patch.dict(
        yumpkg.__salt__, salt_dict
    ):

        expected = {
            "weird-name-1.2.3-1234.5.6.test7tst.x86_64": {
                "old": "20220214-2.1",
                "new": "",
            }
        }
        ret = pkg.removed(
            "test_remove",
            pkgs=[{"weird-name-1.2.3-1234.5.6.test7tst.x86_64.noarch": "20220214-2.1"}],
        )
        call_yum_mock.assert_called_once()
        assert (
            "weird-name-1.2.3-1234.5.6.test7tst.x86_64-20220214-2.1"
            in call_yum_mock.mock_calls[0].args[0]
        )
        assert ret["result"]
        assert ret["changes"] == expected

        call_yum_mock.reset_mock()

        ret = pkg.removed(
            "test_remove",
            pkgs=["weird-name-1.2.3-1234.5.6.test7tst.x86_64.noarch"],
        )
        call_yum_mock.assert_called_once()
        assert (
            "weird-name-1.2.3-1234.5.6.test7tst.x86_64"
            in call_yum_mock.mock_calls[0].args[0]
        )
        assert ret["result"]
        assert ret["changes"] == expected


def test_installed_with_single_normalize_32bit():
    """
    Test pkg.installed of 32bit package with preventing multiple package name normalisation
    """

    list_no_weird_installed = {
        "pkga": "1.0.1",
        "pkgb": "1.0.2",
        "pkgc": "1.0.3",
    }
    list_no_weird_installed_ver_list = {
        "pkga": ["1.0.1"],
        "pkgb": ["1.0.2"],
        "pkgc": ["1.0.3"],
    }
    list_with_weird_installed = {
        "pkga": "1.0.1",
        "pkgb": "1.0.2",
        "pkgc": "1.0.3",
        "xz-devel.i686": "1.2.3",
    }
    list_with_weird_installed_ver_list = {
        "pkga": ["1.0.1"],
        "pkgb": ["1.0.2"],
        "pkgc": ["1.0.3"],
        "xz-devel.i686": ["1.2.3"],
    }
    list_pkgs = MagicMock(
        side_effect=[
            list_no_weird_installed_ver_list,
            {},
            list_no_weird_installed,
            list_no_weird_installed_ver_list,
            list_with_weird_installed,
            list_with_weird_installed,
            list_with_weird_installed_ver_list,
        ]
    )

    salt_dict = {
        "pkg.install": yumpkg.install,
        "pkg.list_pkgs": list_pkgs,
        "pkg.normalize_name": yumpkg.normalize_name,
        "pkg_resource.version_clean": pkg_resource.version_clean,
        "pkg_resource.parse_targets": pkg_resource.parse_targets,
    }

    with patch("salt.modules.yumpkg.list_pkgs", list_pkgs), patch(
        "salt.modules.yumpkg.version_cmp", MagicMock(return_value=0)
    ), patch(
        "salt.modules.yumpkg._call_yum", MagicMock(return_value={"retcode": 0})
    ) as call_yum_mock, patch.dict(
        pkg.__salt__, salt_dict
    ), patch.dict(
        pkg_resource.__salt__, salt_dict
    ), patch.dict(
        yumpkg.__salt__, salt_dict
    ), patch.dict(
        yumpkg.__grains__, {"os": "CentOS", "osarch": "x86_64", "osmajorrelease": 7}
    ):

        expected = {
            "xz-devel.i686": {
                "old": "",
                "new": "1.2.3",
            }
        }
        ret = pkg.installed(
            "test_install",
            pkgs=["xz-devel.i686"],
        )
        call_yum_mock.assert_called_once()
        assert "xz-devel.i686" in call_yum_mock.mock_calls[0].args[0]
        assert ret["result"]
        assert ret["changes"] == expected
