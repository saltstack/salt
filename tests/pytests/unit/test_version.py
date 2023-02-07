"""
tests.pytests.unit.test_version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test salt's regex git describe version parsing
"""
import re

import pytest

import salt.version
from salt.version import (
    SaltStackVersion,
    SaltVersionsInfo,
    system_information,
    versions_report,
)
from tests.support.mock import MagicMock, patch

STRIP_INITIAL_NON_NUMBERS_REGEX = re.compile(r"(?:[^\d]+)?(?P<vs>.*)")


@pytest.mark.parametrize(
    "version_string,full_info, version",
    [
        ("v0.12.0-19-g767d4f9", (0, 12, 0, 0, "", 0, 19, "g767d4f9"), None),
        ("v0.12.0-85-g2880105", (0, 12, 0, 0, "", 0, 85, "g2880105"), None),
        (
            "debian/0.11.1+ds-1-3-ga0afcbd",
            (0, 11, 1, 0, "", 0, 3, "ga0afcbd"),
            "0.11.1+3.ga0afcbd",
        ),
        ("0.12.1", (0, 12, 1, 0, "", 0, 0, None), None),
        ("0.12.1", (0, 12, 1, 0, "", 0, 0, None), None),
        ("0.17.0rc1", (0, 17, 0, 0, "rc", 1, 0, None), None),
        ("v0.17.0rc1-1-g52ebdfd", (0, 17, 0, 0, "rc", 1, 1, "g52ebdfd"), None),
        ("v2014.1.4.1", (2014, 1, 4, 1, "", 0, 0, None), None),
        ("v2014.1.4.1rc3-n/a-abcdefff", (2014, 1, 4, 1, "rc", 3, -1, "abcdefff"), None),
        ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0, None), None),
        ("v3000", (3000, "", 0, 0, None), "3000"),
        ("v3000.0", (3000, "", 0, 0, None), "3000"),
        ("v4518.1", (4518, 1, "", 0, 0, None), "4518.1"),
        ("v3000rc1", (3000, "rc", 1, 0, None), "3000rc1"),
        ("v3000rc1-n/a-abcdefff", (3000, "rc", 1, -1, "abcdefff"), None),
        ("3000-n/a-1e7bc8f", (3000, "", 0, -1, "1e7bc8f"), None),
        ("3000.1-n/a-1e7bc8f", (3000, 1, "", 0, -1, "1e7bc8f"), None),
        (
            "v3000nb20201214010203-1-1e7bc8f",
            (3000, "nb", 20201214010203, 1, "1e7bc8f"),
            None,
        ),
        (
            "v3000.2nb20201214010203-0-1e7bc8f",
            (3000, 2, "nb", 20201214010203, 0, "1e7bc8f"),
            "3000.2nb20201214010203",
        ),
        ("v3006.0", (3006, 0, "", 0, 0, None), "3006.0"),
        ("v3006.0rc1", (3006, 0, "rc", 1, 0, None), "3006.0rc1"),
        ("v3006.1", (3006, 1, "", 0, 0, None), "3006.1"),
        ("v3006.1rc1", (3006, 1, "rc", 1, 0, None), "3006.1rc1"),
    ],
)
def test_version_parsing(version_string, full_info, version):
    saltstack_version = SaltStackVersion.parse(version_string)
    assert saltstack_version.full_info == full_info
    if version is None:
        version = (
            STRIP_INITIAL_NON_NUMBERS_REGEX.search(version_string)
            .group("vs")  # Strip leading non numeric chars
            # Now, make it Wheel metadata 1.2 compliant post release
            .replace("n/a", "0na")
            .replace("-", "+", 1)
            .replace("-", ".", 1)
        )
    assert saltstack_version.string == version


@pytest.mark.parametrize(
    "higher_version,lower_version",
    [
        ("debian/0.11.1+ds-1-3-ga0afcbd", "0.11.1+ds-2"),
        ("v0.12.0-85-g2880105", "v0.12.0-19-g767d4f9"),
        ("v0.17.0rc1-1-g52ebdfd", "0.17.0rc1"),
        ("v0.17.0", "v0.17.0rc1"),
        ("Hydrogen", "0.17.0"),
        ("Helium", "Hydrogen"),
        ("v2014.1.4.1-n/a-abcdefff", "v2014.1.4.1rc3-n/a-abcdefff"),
        ("v2014.1.4.1-1-abcdefff", "v2014.1.4.1-n/a-abcdefff"),
        ("v2016.12.0rc1", "v2016.12.0b1"),
        ("v2016.12.0beta1", "v2016.12.0alpha1"),
        ("v2016.12.0alpha1", "v2016.12.0alpha0"),
        ("v3000.1", "v3000"),
        ("v3000rc2", "v3000rc1"),
        ("v3001", "v3000"),
        ("v4023rc1", "v4022rc1"),
        ("v3000", "v3000rc1"),
        ("v3000", "v2019.2.1"),
        ("v3000.1", "v2019.2.1"),
        # we created v3000.0rc1 tag on repo
        # but we should not be using this
        # version scheme in the future
        # but still adding test for it
        ("v3000", "v3000.0rc1"),
        ("v3000.1rc1", "v3000.0rc1"),
        ("v3000", "v2019.2.1rc1"),
        ("v3001rc1", "v2019.2.1rc1"),
        ("v3002", "v3002nb20201213"),
        ("v3002rc1", "v3002nb20201213"),
        ("v3006.0", "v3006.0rc1"),
        ("v3006.1", "v3006.0rc1"),
        ("v3006.1", "v3006.0"),
    ],
)
def test_version_comparison(higher_version, lower_version):
    assert SaltStackVersion.parse(higher_version) > lower_version
    assert SaltStackVersion.parse(lower_version) < higher_version
    assert SaltStackVersion.parse(lower_version) != higher_version


def test_unparsable_version():
    with pytest.raises(ValueError):
        SaltStackVersion.parse("Drunk")


def test_unparsable_version_from_name():
    with pytest.raises(ValueError):
        SaltStackVersion.from_name("Drunk")


@pytest.mark.parametrize(
    "commit,match",
    [
        ("d6cd1e2bd19e03a81132a23b2025920577f84e37", True),
        ("2880105", True),
        ("v3000.0.1", False),
        ("v0.12.0-85-g2880105", False),
        ("v0.12.0-0-g2880105", False),
    ],
)
def test_sha(commit, match):
    """
    test matching sha's
    """
    ret = SaltStackVersion.git_sha_regex.match(commit)
    if match:
        assert ret is not None
    else:
        assert ret is None


def test_version_report_lines():
    """
    Validate padding in versions report is correct
    """
    # Get a set of all version report name lengths including padding
    versions_report_ret = list(versions_report())
    start_looking_index = versions_report_ret.index("Dependency Versions:") + 1
    line_lengths = {
        len(line.split(":")[0])
        for line in versions_report_ret[start_looking_index:]
        if line != " " and line not in ("System Versions:", "Salt Extensions:")
    }
    # Check that they are all the same size (only one element in the set)
    assert len(line_lengths) == 1


def test_string_new_version():
    """
    Validate string property method
    using new versioning scheme
    """
    maj_ver = "3000"
    ver = SaltStackVersion(major=maj_ver)
    assert not ver.minor
    assert not ver.bugfix
    assert maj_ver == ver.string


def test_string_new_version_minor():
    """
    Validate string property method
    using new versioning scheme alongside
    minor version
    """
    maj_ver = 3000
    min_ver = 1
    ver = SaltStackVersion(major=maj_ver, minor=min_ver)
    assert ver.minor == min_ver
    assert not ver.bugfix
    assert ver.string == "{}.{}".format(maj_ver, min_ver)


def test_string_new_version_minor_as_string():
    """
    Validate string property method
    using new versioning scheme alongside
    minor version
    """
    maj_ver = "3000"
    min_ver = "1"
    ver = SaltStackVersion(major=maj_ver, minor=min_ver)
    assert ver.minor == int(min_ver)
    assert not ver.bugfix
    assert ver.string == "{}.{}".format(maj_ver, min_ver)

    # This only seems to happen on a cloned repo without its tags
    maj_ver = "3000"
    min_ver = ""
    ver = SaltStackVersion(major=maj_ver, minor=min_ver)
    assert ver.minor is None, "{!r} is not {!r}".format(ver.minor, min_ver)
    assert not ver.bugfix
    assert ver.string == maj_ver


def test_string_old_version():
    """
    Validate string property method
    using old versioning scheme alongside
    minor version
    """
    maj_ver = "2019"
    min_ver = "2"
    ver = SaltStackVersion(major=maj_ver, minor=min_ver)
    assert ver.bugfix == 0
    assert ver.string == "{}.{}.0".format(maj_ver, min_ver)


@pytest.mark.parametrize(
    "vstr,noc_info",
    [
        ("v2014.1.4.1rc3-n/a-abcdefff", (2014, 1, 4, 1, "rc", 3, -1)),
        ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0)),
        ("v3000", (3000, "", 0, 0)),
        ("v3000.0", (3000, "", 0, 0)),
        ("v4518.1", (4518, 1, "", 0, 0)),
        ("v3000rc1", (3000, "rc", 1, 0)),
        ("v3000rc1-n/a-abcdefff", (3000, "rc", 1, -1)),
        ("v3000nb1-0-abcdefff", (3000, "nb", 1, 0)),
    ],
)
def test_noc_info(vstr, noc_info):
    """
    Test noc_info property method
    """
    saltstack_version = SaltStackVersion.parse(vstr)
    assert saltstack_version.noc_info, noc_info
    assert len(saltstack_version.noc_info) == len(noc_info)


@pytest.mark.parametrize(
    "vstr,full_info",
    [
        ("v2014.1.4.1rc3-n/a-abcdefff", (2014, 1, 4, 1, "rc", 3, -1, "abcdefff")),
        ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0, None)),
        ("v3000", (3000, "", 0, 0, None)),
        ("v3000.0", (3000, "", 0, 0, None)),
        ("v4518.1", (4518, 1, "", 0, 0, None)),
        ("v3000rc1", (3000, "rc", 1, 0, None)),
        ("v3000rc1-n/a-abcdefff", (3000, "rc", 1, -1, "abcdefff")),
        ("v3000nb20201214-0-gabcdefff", (3000, "nb", 20201214, 0, "gabcdefff")),
    ],
)
def test_full_info(vstr, full_info):
    """
    Test full_info property method
    """
    saltstack_version = SaltStackVersion.parse(vstr)
    assert saltstack_version.full_info, full_info
    assert len(saltstack_version.full_info) == len(full_info)


@pytest.mark.parametrize(
    "vstr,full_info",
    [
        ("v2014.1.4.1rc3-n/a-abcdefff", (2014, 1, 4, 1, "rc", 3, -1, "abcdefff")),
        ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0, None)),
        ("v3000", (3000, None, None, 0, "", 0, 0, None)),
        ("v3000.0", (3000, 0, None, 0, "", 0, 0, None)),
        ("v4518.1", (4518, 1, None, 0, "", 0, 0, None)),
        ("v3000rc1", (3000, None, None, 0, "rc", 2, 0, None)),
        ("v3000rc1-n/a-abcdefff", (3000, None, None, 0, "rc", 1, -1, "abcdefff")),
        ("v3000nb2-0-abcdefff", (3000, None, None, 0, "nb", 2, 0, "abcdefff")),
    ],
)
def test_full_info_all_versions(vstr, full_info):
    """
    Test full_info_all_versions property method
    """
    saltstack_version = SaltStackVersion.parse(vstr)
    assert saltstack_version.full_info_all_versions
    assert len(saltstack_version.full_info_all_versions) == len(full_info)


@pytest.mark.parametrize(
    "major,minor,tag,expected",
    [
        (3000, None, b"v3000.0rc2-12-g44fe283a77\n", "3000rc2-12-g44fe283a77"),
        (3000, None, b"v3000.0rc2-0-g44fe283a77\n", "3000rc2"),
        (3000, None, b"v3000", "3000"),
        (3000, None, b"1234567", "3000-0na-1234567"),
        (2019, 2, b"v2019.2.0rc2-12-g44fe283a77\n", "2019.2.0rc2-12-g44fe283a77"),
        (2019, 2, b"v2019.2.0", "2019.2.0"),
        (2019, 2, b"afc9830198dj", "2019.2.0-0na-afc9830198dj"),
    ],
)
def test_discover_version(major, minor, tag, expected):
    """
    Test call to __discover_version
    when using different versions
    """
    salt_ver = SaltStackVersion(major=major, minor=minor, bugfix=None)
    attrs = {
        "communicate.return_value": (tag, b""),
        "returncode.return_value": 0,
    }
    proc_ret = MagicMock(**attrs)
    proc_mock = patch("subprocess.Popen", return_value=proc_ret)
    patch_os = patch("os.path.exists", return_value=True)

    with proc_mock, patch_os:
        ret = getattr(salt.version, "__discover_version")(salt_ver)
    assert ret == expected


@pytest.mark.parametrize(
    "major,minor,bugfix",
    [
        (3000, None, None),
        (3000, 1, None),
        (3001, 0, None),
    ],
)
def test_info_new_version(major, minor, bugfix):
    """
    test info property method with new versioning scheme
    """
    ver = SaltStackVersion(major=major, minor=minor, bugfix=bugfix)
    if minor:
        assert ver.info == (major, minor)
    else:
        assert ver.info == (major,)


@pytest.mark.parametrize(
    "major,minor,bugfix",
    [
        (2019, 2, 1),
        (2018, 3, 0),
        (2017, 7, None),
    ],
)
def test_info_old_version(major, minor, bugfix):
    """
    test info property method with old versioning scheme
    """
    ver = SaltStackVersion(major=major, minor=minor, bugfix=bugfix)
    if bugfix is None:
        assert ver.info == (major, minor, 0, 0)
    else:
        assert ver.info == (major, minor, bugfix, 0)


def test_bugfix_string():
    """
    test when bugfix is an empty string
    """
    ret = SaltStackVersion(3000, 1, "", 0, 0, None)
    assert ret.info == (3000, 1)
    assert ret.minor == 1
    assert ret.bugfix is None


@pytest.mark.parametrize(
    "version_tuple,expected",
    [
        (
            (3000, 1, None, None, "", 0, 0, None),
            "<SaltStackVersion name='Neon' major=3000 minor=1>",
        ),
        (
            (3000, 0, None, None, "", 0, 0, None),
            "<SaltStackVersion name='Neon' major=3000>",
        ),
        (
            (2019, 2, 3, None, "", 0, 0, None),
            "<SaltStackVersion name='Fluorine' major=2019 minor=2 bugfix=3>",
        ),
        (
            (2019, 2, 3, None, "rc", 1, 0, None),
            "<SaltStackVersion name='Fluorine' major=2019 minor=2 bugfix=3 rc=1>",
        ),
        (
            (2019, 2, 3, None, "nb", 20201214, 0, None),
            "<SaltStackVersion name='Fluorine' major=2019 minor=2 bugfix=3"
            " nb=20201214>",
        ),
    ],
)
def test_version_repr(version_tuple, expected):
    """
    Test SaltStackVersion repr for both date
    and new versioning scheme
    """
    assert repr(SaltStackVersion(*version_tuple)) == expected


def test_previous_and_next_releases():
    with patch.multiple(
        SaltVersionsInfo,
        _previous_release=None,
        _next_release=None,
        _current_release=SaltVersionsInfo.CALIFORNIUM,
    ):
        assert SaltVersionsInfo.current_release() == SaltVersionsInfo.CALIFORNIUM
        assert SaltVersionsInfo.next_release() == SaltVersionsInfo.EINSTEINIUM
        assert SaltVersionsInfo.previous_release() == SaltVersionsInfo.BERKELIUM

    with patch.multiple(
        SaltVersionsInfo,
        _previous_release=None,
        _next_release=None,
        _current_release=SaltVersionsInfo.NEPTUNIUM,
    ):
        assert SaltVersionsInfo.current_release() == SaltVersionsInfo.NEPTUNIUM
        assert SaltVersionsInfo.next_release() == SaltVersionsInfo.PLUTONIUM
        assert SaltVersionsInfo.previous_release() == SaltVersionsInfo.URANIUM


@pytest.mark.skip_unless_on_linux
def test_system_version_linux():
    """
    version.system_version on Linux
    """

    with patch(
        "distro.linux_distribution",
        MagicMock(return_value=("Manjaro Linux", "20.0.2", "Lysia")),
    ):
        versions = [item for item in system_information()]
        version = ("version", "Manjaro Linux 20.0.2 Lysia")
        assert version in versions

    with patch(
        "distro.linux_distribution",
        MagicMock(return_value=("Debian GNU/Linux", "9", "stretch")),
    ):
        versions = [item for item in system_information()]
        version = ("version", "Debian GNU/Linux 9 stretch")
        assert version in versions

    with patch(
        "distro.linux_distribution",
        MagicMock(return_value=("Debian GNU/Linux", "10", "buster")),
    ):
        versions = [item for item in system_information()]
        version = ("version", "Debian GNU/Linux 10 buster")
        assert version in versions

    with patch(
        "distro.linux_distribution",
        MagicMock(return_value=("CentOS Linux", "7", "Core")),
    ):
        versions = [item for item in system_information()]
        version = ("version", "CentOS Linux 7 Core")
        assert version in versions

    with patch(
        "distro.linux_distribution",
        MagicMock(return_value=("CentOS Linux", "8", "Core")),
    ):
        versions = [item for item in system_information()]
        version = ("version", "CentOS Linux 8 Core")
        assert version in versions

    with patch(
        "distro.linux_distribution",
        MagicMock(return_value=("OpenSUSE Leap", "15.1", "")),
    ):
        versions = [item for item in system_information()]
        version = ("version", "OpenSUSE Leap 15.1 ")
        assert version in versions


@pytest.mark.skip_unless_on_darwin
def test_system_version_osx():
    """
    version.system_version on OS X
    """

    with patch(
        "platform.mac_ver",
        MagicMock(return_value=("10.15.2", ("", "", ""), "x86_64")),
    ):
        versions = [item for item in system_information()]
        version = ("version", "10.15.2 x86_64")
        assert version in versions


@pytest.mark.skip_unless_on_windows
def test_system_version_windows():
    """
    version.system_version on Windows
    """

    with patch(
        "platform.win32_ver",
        return_value=("10", "10.0.14393", "SP0", "Multiprocessor Free"),
    ), patch("win32api.RegOpenKey", MagicMock()), patch(
        "win32api.RegQueryValueEx",
        MagicMock(return_value=("Windows Server 2016 Datacenter", 1)),
    ):
        versions = [item for item in system_information()]
        version = ("version", "2016Server 10.0.14393 SP0 Multiprocessor Free")
        assert version in versions


def test_versions_report_includes_salt_extensions():
    with patch(
        "salt.version.extensions_information", return_value={"foo-bar-ext": "1.0"}
    ):
        versions_information = salt.version.versions_information()
        assert "Salt Extensions" in versions_information
        assert "foo-bar-ext" in versions_information["Salt Extensions"]
        assert versions_information["Salt Extensions"]["foo-bar-ext"] == "1.0"


def test_versions_report_no_extensions_available():
    with patch("salt.utils.entrypoints.iter_entry_points", return_value=()):
        versions_information = salt.version.versions_information()
        assert "Salt Extensions" not in versions_information


@pytest.mark.parametrize(
    "version_str,expected_str,expected_name",
    [
        ("2014.1.4", "2014.1.4", "Hydrogen"),
        ("3000.1", "3000.1", "Neon"),
        ("3005", "3005", "Phosphorus"),
        ("3006", "3006.0", "Sulfur"),
        ("3015.1", "3015.1", "Manganese"),
        ("3109.3", "3109.3", None),
    ],
)
def test_parsed_version_name(version_str, expected_str, expected_name):
    """
    Test all versioning schemes name attribute.

    The old, new, and dot zero, must properly set the version name attribut
    test info property method with new versioning scheme
    """
    ver = SaltStackVersion.parse(version_str)
    assert str(ver) == expected_str
    if expected_name:
        assert ver.name == expected_name
    else:
        assert ver.name is None
