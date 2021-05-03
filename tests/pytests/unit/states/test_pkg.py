import os

import pytest
import salt.modules.beacons as beaconmod
import salt.states.beacon as beaconstate
import salt.states.pkg as pkg
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        pkg: {
            "__env__": "base",
            "__salt__": {},
            "__grains__": {"os": "CentOS"},
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        },
        beaconstate: {"__salt__": {}, "__opts__": {}},
        beaconmod: {"__salt__": {}, "__opts__": {}},
    }


@pytest.fixture(scope="module")
def pkgs():
    return {
        "pkga": {"old": "1.0.1", "new": "2.0.1"},
        "pkgb": {"old": "1.0.2", "new": "2.0.2"},
        "pkgc": {"old": "1.0.3", "new": "2.0.3"},
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
            ret = pkg.uptodate("dummy", test=True, pkgs=[pkgname for pkgname in pkgs],)
            assert ret["result"]
            assert ret["changes"] == pkgs

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate("dummy", test=True, pkgs=[pkgname for pkgname in pkgs],)
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
            ret = pkg.uptodate("dummy", test=True, pkgs=[pkgname for pkgname in pkgs],)
            assert ret["result"]
            assert ret["changes"] == {}

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate("dummy", test=True, pkgs=[pkgname for pkgname in pkgs],)
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
            ret = pkg.uptodate("dummy", test=True, pkgs=[pkgname for pkgname in pkgs],)
            assert not ret["result"]
            assert ret["changes"] == {}

        # Run state with test=true
        with patch.dict(pkg.__opts__, {"test": True}):
            ret = pkg.uptodate("dummy", test=True, pkgs=[pkgname for pkgname in pkgs],)
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
        ("> 1.0.0, < 15.0.0, != 14.0.1", ["1.0.0", "14.0.1", "16.0.0", "2.0.0"], True,),
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
    msg = "installed_versions: {}, operator: {}, version: {}, expected_result: {}".format(
        installed_versions, operator, version, expected_result
    )
    assert expected_result == pkg._fulfills_version_spec(
        installed_versions, operator, version
    )


def test_mod_beacon():
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
                "comment": "pkg.latest does not work with the mod_beacon state function",
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

    with pytest.helpers.temp_directory() as tempdir:
        sock_dir = os.path.join(tempdir, "test-socks")
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
