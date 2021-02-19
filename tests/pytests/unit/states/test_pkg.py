import pytest
import salt.states.pkg as pkg
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pkg: {"__grains__": {"os": "CentOS"}}}


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
