"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import random
import string
import textwrap

import pytest

import salt.modules.cmdmod
import salt.modules.rpm_lowpkg as rpm_lowpkg
import salt.utils.path
from tests.support.mock import MagicMock, patch

try:
    import rpm

    HAS_RPM = True
except ImportError:
    HAS_RPM = False


def _called_with_root(mock):
    cmd = " ".join(mock.call_args[0][0])
    return cmd.startswith("rpm --root /")


@pytest.fixture
def configure_loader_modules():
    return {rpm_lowpkg: {"rpm": MagicMock(return_value=MagicMock)}}


def test___virtual___openeuler():
    patch_which = patch("salt.utils.path.which", return_value=True)
    with patch.dict(
        rpm_lowpkg.__grains__, {"os": "openEuler", "os_family": "openEuler"}
    ), patch_which:
        assert rpm_lowpkg.__virtual__() == "lowpkg"


def test___virtual___issabel_pbx():
    patch_which = patch("salt.utils.path.which", return_value=True)
    with patch.dict(
        rpm_lowpkg.__grains__, {"os": "Issabel Pbx", "os_family": "IssabeL PBX"}
    ), patch_which:
        assert rpm_lowpkg.__virtual__() == "lowpkg"


def test___virtual___virtuozzo():
    patch_which = patch("salt.utils.path.which", return_value=True)
    with patch.dict(
        rpm_lowpkg.__grains__, {"os": "virtuozzo", "os_family": "VirtuoZZO"}
    ), patch_which:
        assert rpm_lowpkg.__virtual__() == "lowpkg"


def test___virtual___with_no_rpm():
    patch_which = patch("salt.utils.path.which", return_value=False)
    ret = rpm_lowpkg.__virtual__()
    assert isinstance(ret, tuple)
    assert ret[0] is False


# 'list_pkgs' function tests: 2


def test_list_pkgs():
    """
    Test if it list the packages currently installed in a dict
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run": mock}):
        assert rpm_lowpkg.list_pkgs() == {}
        assert not _called_with_root(mock)


def test_list_pkgs_root():
    """
    Test if it list the packages currently installed in a dict,
    called with root parameter
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run": mock}):
        rpm_lowpkg.list_pkgs(root="/")
        assert _called_with_root(mock)


# 'verify' function tests: 2


def test_verify():
    """
    Test if it runs an rpm -Va on a system, and returns the
    results in a dict
    """
    mock = MagicMock(
        return_value={"stdout": "", "stderr": "", "retcode": 0, "pid": 12345}
    )
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run_all": mock}):
        assert rpm_lowpkg.verify("httpd") == {}
        assert not _called_with_root(mock)


def test_verify_root():
    """
    Test if it runs an rpm -Va on a system, and returns the
    results in a dict, called with root parameter
    """
    mock = MagicMock(
        return_value={"stdout": "", "stderr": "", "retcode": 0, "pid": 12345}
    )
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run_all": mock}):
        rpm_lowpkg.verify("httpd", root="/")
        assert _called_with_root(mock)


# 'file_list' function tests: 2


def test_file_list():
    """
    Test if it list the files that belong to a package.
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run": mock}):
        assert rpm_lowpkg.file_list("httpd") == {"errors": [], "files": []}
        assert not _called_with_root(mock)


def test_file_list_root():
    """
    Test if it list the files that belong to a package, using the
    root parameter.
    """

    mock = MagicMock(return_value="")
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run": mock}):
        rpm_lowpkg.file_list("httpd", root="/")
        assert _called_with_root(mock)


# 'file_dict' function tests: 2


def test_file_dict():
    """
    Test if it list the files that belong to a package
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run": mock}):
        assert rpm_lowpkg.file_dict("httpd") == {"errors": [], "packages": {}}
        assert not _called_with_root(mock)


def test_file_dict_root():
    """
    Test if it list the files that belong to a package
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run": mock}):
        rpm_lowpkg.file_dict("httpd", root="/")
        assert _called_with_root(mock)


# 'owner' function tests: 1


def test_owner():
    """
    Test if it return the name of the package that owns the file.
    """
    assert rpm_lowpkg.owner() == ""

    ret = "file /usr/bin/salt-jenkins-build is not owned by any package"
    mock = MagicMock(return_value=ret)
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run_stdout": mock}):
        assert rpm_lowpkg.owner("/usr/bin/salt-jenkins-build") == ""
        assert not _called_with_root(mock)

    ret = {
        "/usr/bin/vim": "vim-enhanced-7.4.160-1.e17.x86_64",
        "/usr/bin/python": "python-2.7.5-16.e17.x86_64",
    }
    mock = MagicMock(
        side_effect=[
            "python-2.7.5-16.e17.x86_64",
            "vim-enhanced-7.4.160-1.e17.x86_64",
        ]
    )
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run_stdout": mock}):
        assert rpm_lowpkg.owner("/usr/bin/python", "/usr/bin/vim") == ret
        assert not _called_with_root(mock)


def test_owner_root():
    """
    Test if it return the name of the package that owns the file,
    using the parameter root.
    """
    assert rpm_lowpkg.owner() == ""

    ret = "file /usr/bin/salt-jenkins-build is not owned by any package"
    mock = MagicMock(return_value=ret)
    with patch.dict(rpm_lowpkg.__salt__, {"cmd.run_stdout": mock}):
        rpm_lowpkg.owner("/usr/bin/salt-jenkins-build", root="/")
        assert _called_with_root(mock)


# 'checksum' function tests: 2


def test_checksum():
    """
    Test if checksum validate as expected
    """
    ret = {
        "file1.rpm": True,
        "file2.rpm": False,
        "file3.rpm": False,
    }

    mock = MagicMock(side_effect=[True, 0, True, 1, False, 0])
    with patch.dict(
        rpm_lowpkg.__salt__, {"file.file_exists": mock, "cmd.retcode": mock}
    ):
        assert rpm_lowpkg.checksum("file1.rpm", "file2.rpm", "file3.rpm") == ret
        assert not _called_with_root(mock)


def test_checksum_root():
    """
    Test if checksum validate as expected, using the parameter
    root
    """
    mock = MagicMock(side_effect=[True, 0])
    with patch.dict(
        rpm_lowpkg.__salt__, {"file.file_exists": mock, "cmd.retcode": mock}
    ):
        rpm_lowpkg.checksum("file1.rpm", root="/")
        assert _called_with_root(mock)


@pytest.mark.skipif(not HAS_RPM, reason="python rpm module not available")
def test_version_cmp_rpm_lib():
    """
    Test package version when each library is installed
    """
    patch_cmd = patch.dict(
        rpm_lowpkg.__salt__, {"cmd.run_all": salt.modules.cmdmod.run_all}
    )
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", True)

    with patch_rpm, patch_cmd:
        assert rpm_lowpkg.version_cmp("1", "2") == -1
        assert rpm_lowpkg.version_cmp("2.9.1-6.el7_2.3", "2.9.1-6.el7.4") == -1
        assert rpm_lowpkg.version_cmp("3.2", "3.0") == 1
        assert rpm_lowpkg.version_cmp("3.0", "3.0") == 0
        assert rpm_lowpkg.version_cmp("1:2.9.1-6.el7_2.3", "2.9.1-6.el7.4") == 1
        assert rpm_lowpkg.version_cmp("1:2.9.1-6.el7_2.3", "1:2.9.1-6.el7.4") == -1
        assert rpm_lowpkg.version_cmp("2:2.9.1-6.el7_2.3", "1:2.9.1-6.el7.4") == 1
        assert rpm_lowpkg.version_cmp("3:2.9.1-6.el7.4", "3:2.9.1-6.el7.4") == 0
        assert rpm_lowpkg.version_cmp("3:2.9.1-6.el7.4", "3:2.9.1-7.el7.4") == -1
        assert rpm_lowpkg.version_cmp("3:2.9.1-8.el7.4", "3:2.9.1-7.el7.4") == 1
        assert rpm_lowpkg.version_cmp("3.23-6.el9", "3.23") == 0
        assert rpm_lowpkg.version_cmp("3.23", "3.23-6.el9") == 0
        assert (
            rpm_lowpkg.version_cmp("release_web_294-6", "release_web_294_applepay-1")
            == -1
        )


def test_version_cmp_rpm():
    """
    Test package version if RPM-Python is installed

    :return:
    """
    mock_label = MagicMock(return_value=-1)
    mock_log = MagicMock()
    patch_label = patch("salt.modules.rpm_lowpkg.rpm.labelCompare", mock_label)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", True)
    with patch_label, patch_rpm, patch_log:
        assert -1 == rpm_lowpkg.version_cmp("1", "2")
        assert not mock_log.warning.called
        assert mock_label.called


def test_version_cmp_python():
    """
    Test package version if falling back to python

    :return:
    """
    mock_log = MagicMock()
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)

    with patch_rpm, patch_log:
        assert -1 == rpm_lowpkg.version_cmp("1", "2")
        assert not mock_log.warning.called
        assert mock_log.info.called
        assert (
            mock_log.info.mock_calls[0][1][0]
            == "Install a package that provides rpm.labelCompare for faster version comparisons."
        )


def _parse_label(label: str):
    """Split full label into (epoch, version, release) for rpm.labelCompare."""
    epoch = None
    version = None
    release = None
    if ":" in label:
        epoch, rest = label.split(":", 1)
    else:
        rest = label
    if "-" in rest:
        version, release = rest.split("-", 1)
    else:
        version = rest
    return (epoch, version, release)


VERSION_CASES = [
    # Basic equality and ordering
    ("1", "1", 0),
    ("1", "2", -1),
    ("2", "1", 1),
    ("1.0", "1.0", 0),
    ("1.0", "2.0", -1),
    ("2.0", "1.0", 1),
    ("2.0.1", "2.0.1", 0),
    ("2.0", "2.0.1", -1),
    ("2.0.1", "2.0", 1),
    # Epoch precedence
    ("0:1.0-1", "1.0-1", 0),
    ("1:1.0-1", "0:9.9-9", 1),
    ("0:9.9-9", "1:1.0-1", -1),
    ("02:1.0-1", "2:1.0-1", 0),
    # Version vs release precedence (version decides before release)
    ("1.0.1-1", "1.0-9", 1),
    ("1.0-9", "1.0.1-1", -1),
    # Numeric vs numeric
    ("2.0-1", "10.0-1", -1),
    ("10.0-1", "2.0-1", 1),
    ("2.10-1", "2.2-1", 1),
    ("2.02-1", "2.2-1", 0),
    ("10.0001", "10.0001", 0),
    ("10.0001", "10.1", 0),
    ("10.1", "10.0001", 0),
    ("10.0001", "10.0039", -1),
    ("10.0039", "10.0001", 1),
    ("010.0039", "10.0039", 0),
    ("4.999.9", "5.0", -1),
    ("5.0", "4.999.9", 1),
    # Long numeric segments
    ("2.12345678901234567890-1", "2.12345678901234567891-1", -1),
    # Date-like numbers
    ("20101121", "20101121", 0),
    ("20101121", "20101122", -1),
    ("20101122", "20101121", 1),
    # 'p' in numeric-ish segments (treated as alphabetic break)
    ("5.5p1", "5.5p1", 0),
    ("5.5p1", "5.5p2", -1),
    ("5.5p2", "5.5p1", 1),
    ("5.5p10", "5.5p10", 0),
    ("5.5p1", "5.5p10", -1),
    ("5.5p10", "5.5p1", 1),
    ("5.5p2", "5.6p1", -1),
    ("5.6p1", "5.5p2", 1),
    ("5.6p1", "6.5p1", -1),
    ("6.5p1", "5.6p1", 1),
    # Dot before alpha: dots split segments but alpha still compares after
    ("2.0.1a", "2.0.1a", 0),
    ("2.0.1a", "2.0.1", 1),
    ("2.0.1", "2.0.1a", -1),
    ("6.0.rc1", "6.0", 1),
    ("6.0", "6.0.rc1", -1),
    # other alphanumeric
    ("10xyz", "10.1xyz", -1),
    ("10.1xyz", "10xyz", 1),
    ("xyz10", "xyz10", 0),
    ("xyz10", "xyz10.1", -1),
    ("xyz10.1", "xyz10", 1),
    # capital letters
    ("A", "A", 0),
    ("A", "B", -1),
    ("B", "a", -1),
    ("A", "a", -1),
    ("Ab", "Ab", 0),
    ("A0", "A0", 0),
    ("A", "a", -1),
    ("a", "A", 1),
    ("Ab", "aB", -1),
    ("A.1", "a.1", -1),
    ("Abc1", "abc1", -1),
    ("abc1", "Abc1", 1),
    ("A1b2", "A1B2", 1),
    ("1A", "1a", -1),
    ("1.A", "1.a", -1),
    ("1.A.2", "1.a.2", -1),
    ("1.0A", "1.0a", -1),
    ("1.0a", "1.0A", 1),
    ("1.0Aalpha", "1.0aalpha", -1),
    # Alphanumeric segment vs pure-numeric segment ordering
    # Alphanumeric segments (start with letters) should sort after pure-numeric versions;
    # dotted alpha+numeric combos compare as expected and equality is preserved.
    ("xyz.4", "xyz.4", 0),
    ("xyz.4", "8", -1),
    ("8", "xyz.4", 1),
    ("xyz.4", "2", -1),
    ("2", "xyz.4", 1),
    # Alphabetic tails and mixed alpha-numeric comparisons
    # Alphabetic suffixes are compared lexicographically; when alpha tails share a prefix
    # the shorter tail sorts earlier. Mixed numeric+alpha+numeric tokens use the numeric
    # prefix first, then alphabetic ordering to break ties.
    ("a", "a", 0),
    ("2a-1", "2-1", 1),
    ("2-1", "2a-1", -1),
    ("2alpha-1", "2beta-1", -1),
    ("2.0.1a", "2.0.1a", 0),
    ("alpha-1", "beta-1", -1),
    ("beta-1", "alpha-1", 1),
    ("10b2", "10a1", 1),
    ("10a2", "10b2", -1),
    ("1.0aa", "1.0aa", 0),
    ("1.0a", "1.0aa", -1),
    ("1.0aa", "1.0a", 1),
    ("1.0~A", "1.0~a", -1),
    ("1.0~a", "1.0~A", 1),
    ("1.0^A", "1.0^a", -1),
    ("1.0^a", "1.0^A", 1),
    ("1.0+A", "1.0+a", -1),
    ("1.0+a", "1.0+A", 1),
    # Tilde: pre-release; sorts older than anything without it
    ("2.0~beta-1", "2.0-1", -1),
    ("2.0-1", "2.0~beta-1", 1),
    ("2.0~beta-1", "2.0~rc-1", -1),  # beta < rc lexicographically
    ("1.0~rc1", "1.0~rc1", 0),
    ("1.0~rc1", "1.0", -1),
    ("1.0", "1.0~rc1", 1),
    ("1.0~rc1", "1.0~rc2", -1),
    ("1.0~rc2", "1.0~rc1", 1),
    # Tilde chaining
    ("1.0~rc1~git123", "1.0~rc1~git123", 0),
    ("1.0~rc1~git123", "1.0~rc1", -1),
    ("1.0~rc1", "1.0~rc1~git123", 1),
    # Caret: post-release; newer than base but lower than next increment
    ("1.0^", "1.0^", 0),
    ("1.0^", "1.0", 1),
    ("1.0", "1.0^", -1),
    ("1.0^git1", "1.0", 1),
    ("1.0", "1.0^git1", -1),
    ("1.0^git1", "1.0^git1", 0),
    ("1.0^git1", "1.0^git2", -1),
    ("1.0^git2", "1.0^git1", 1),
    ("1.0^git9", "1.0.1", -1),  # caret block still less than next numeric bump
    ("1.0.1", "1.0^git9", 1),
    ("1.0^git1", "1.01", -1),
    ("1.01", "1.0^git1", 1),
    ("1.0^20160101", "1.0^20160101", 0),
    ("1.0^20160101", "1.0.1", -1),
    ("1.0.1", "1.0^20160101", 1),
    ("1.0^20160101^git1", "1.0^20160101^git1", 0),
    ("1.0^20160102", "1.0^20160101^git1", 1),
    ("1.0^20160101^git1", "1.0^20160102", -1),
    # Caret + tilde
    ("1.0~rc1^git1", "1.0~rc1", 1),
    ("1.0~rc1", "1.0~rc1^git1", -1),
    ("1.0^git1~pre", "1.0^git1", -1),
    ("1.0^git1", "1.0^git1~pre", 1),
    # Separators: '.', '_', '+' are equivalent and collapse
    ("2_0", "2.0", 0),
    ("2.0", "2_0", 0),
    ("2+0", "2.0", 0),
    ("2.0", "2+0", 0),
    ("2_0", "2+0", 0),
    # Collapsing multiple separators
    ("1+.+0", "1.0", 0),
    ("1_._0", "1.0", 0),
    ("1+_+0", "1.0", 0),
    # Plus/underscore equivalences at segment edges
    ("a+", "a_", 0),
    ("a+", "a+", 0),
    ("a+", "a_", 0),
    ("a_", "a+", 0),
    ("+a", "+a", 0),
    ("+a", "_a", 0),
    ("_a", "+a", 0),
    ("+_", "+_", 0),
    ("+_", "_+", 0),
    ("+", "_", 0),
    ("_", "+", 0),
    # Mixed separators with numbers
    ("1+2", "1.2", 0),
    ("1_2", "1.2", 0),
    ("1+_2", "1.2", 0),
    # Release segment variations
    ("2.0-1-alpha", "2.0-1-beta", -1),
    ("2.0-1-beta", "2.0-1-alpha", 1),
    ("2.0-1-alpha-1", "2.0-1-alpha-2", -1),
    ("2.0-1.alpha-beta.1", "2.0-1.alpha-beta.2", -1),
    ("2.0-1.alpha-beta.2", "2.0-1.alpha-beta.1", 1),
    ("2.0-1.alpha-beta.gamma", "2.0-1.alpha-beta.delta", 1),
    # Release containing periods + trailing zeros (RPM: longer wins, even if .0)
    ("2.0-1.0.0", "2.0-1.0", 1),
    ("2.0-1.0.1", "2.0-1.0", 1),
    ("2.0-1.alpha.1", "2.0-1.alpha.2", -1),
    ("2.0-1.alpha.01", "2.0-1.alpha.1", 0),
    # Empty release equivalence and ordering
    ("2.0", "2.0-", 0),
    ("2.0-", "2.0-1", 0),
    # Different number of segments
    ("1.0", "1.0.1", -1),
    ("1.0.1", "1.0", 1),
    ("1.0", "1.0.0", -1),
    ("1.0.0.1", "1.0", 1),
    ("1.0a", "1.0.a", 0),
    # Different number of release segments
    ("1.0-1", "1.0-1.1", -1),
    ("1.0-1.1", "1.0-1", 1),
    ("1.0-1", "1.0-1.0", -1),
    ("1.0-1.0.1", "1.0-1", 1),
    # Mixed alpha/numeric with extra segments in version
    ("1.0alpha", "1.0alpha.1", -1),
    ("1.0alpha.1", "1.0alpha", 1),
    ("1.0alpha.0", "1.0alpha", 1),
    # Mixed alpha/numeric with extra segments in release
    ("1.0-1-alpha", "1.0-1-alpha.1", -1),
    ("1.0-1-alpha.1", "1.0-1-alpha", 1),
    ("1.0-1-alpha.0", "1.0-1-alpha", 1),
    # Multiple hyphens inside the release
    ("1.0-1-alpha-beta", "1.0-1-alpha-gamma", -1),
    ("1.0-1-alpha-gamma", "1.0-1-alpha-beta", 1),
    ("1.0-1-alpha-beta", "1.0-1-alpha", 1),
    ("1.0-1-alpha", "1.0-1-alpha-beta", -1),
    ("1.0-1-alpha-1", "1.0-1-alpha", 1),
    ("1.0-1-alpha", "1.0-1-alpha-1", -1),
    ("2.0-1-alpha-beta.2", "2.0-1-alpha-beta.10", -1),
    ("2.0-1-alpha-beta.10", "2.0-1-alpha-beta.2", 1),
    # Releases containing multiple numeric hyphen segments
    ("1.0-1-1", "1.0-1-2", -1),
    ("1.0-1-2", "1.0-1-1", 1),
    ("1.0-1-01", "1.0-1-1", 0),
    # Releases with separators and multiple operator segments
    ("1.0-1.alpha-beta-1", "1.0-1.alpha-beta-2", -1),
    ("1.0-1.alpha-beta-2", "1.0-1.alpha-beta-1", 1),
    # Explicit empty vs multiple-hyphen release forms
    ("1.0-", "1.0-1-alpha", 0),
    ("1.0-1-alpha", "1.0-", 0),
    # Longer release wins when numeric/alpha tie in earlier segments
    ("3.0-1.0.0-0", "3.0-1.0.0", 1),
    ("3.0-1.0.0", "3.0-1.0.0-0", -1),
    # Same version, one side has no release -> treat as equal
    ("1.0-1", "1.0", 0),
    ("1.0", "1.0-1", 0),
    ("2.3.4-5", "2.3.4", 0),
    ("2.3.4", "2.3.4-5", 0),
    # Different versions, release ignored if one side missing -> version decides
    ("1.0-2", "1.1", -1),
    ("1.1", "1.0-2", 1),
    ("2.0-3", "2.0.1", -1),
    ("2.0.1", "2.0-3", 1),
    # Epoch differences still take precedence even when release missing
    ("1:1.0-1", "1.0", 1),
    ("1.0", "1:1.0-1", -1),
    ("0:2.0-1", "1:1.9", -1),
    ("1:1.9", "0:2.0-1", 1),
    # Both sides have version segments that compare alphabetically; release ignored when missing
    ("1.0a-1", "1.0a", 0),
    ("1.0a", "1.0a-2", 0),
    ("1.0~rc1-1", "1.0~rc1", 0),
    ("1.0~rc1", "1.0~rc1-1", 0),
    # Operator blocks: caret/tilde interactions, release ignored when missing
    ("1.0^git1-1", "1.0^git1", 0),
    ("1.0^git1", "1.0^git1-2", 0),
    (
        "1.0~beta-1",
        "1.0",
        -1,
    ),  # tilde makes version older than base even if release present on left
    ("1.0", "1.0~beta-1", 1),
    # One side has complex release, other has no release; version decides when different
    ("2.0.1-10.alpha", "2.0.1", 0),
    ("2.0.1", "2.0.1-10.alpha", 0),
    ("2.0.2-1", "2.0.10", -1),
    ("2.0.10", "2.0.2-1", 1),
    # Special chars in wild
    ("2.0_git20210101-1", "2.0_git20201231-1", 1),
    ("2.0+dfsg-1", "2.0-1", 1),
    # More separator/operator chains
    ("1.0+rc1", "1.0_rc1", 0),
    ("1.0+rc1", "1.0.rc1", 0),
    ("1.0+rc1^git1", "1.0.rc1^git1", 0),
    ("1.0~beta+1", "1.0~beta.1", 0),
    ("1.0~beta_1", "1.0~beta.1", 0),
    # Caret blocks vs longer alpha tail
    ("1.0^a", "1.0a", -1),
    ("1.0a", "1.0^a", 1),
    # Tilde vs caret at same position
    ("1.0~a", "1.0^a", -1),  # tilde is always older
    ("1.0^a", "1.0~a", 1),
    # Chained: tilde inside caret block
    ("1.0^a~b", "1.0^a", -1),
    ("1.0^a", "1.0^a~b", 1),
    # Chained: caret after tilde block
    ("1.0~a^b", "1.0~a", 1),
    ("1.0~a", "1.0~a^b", -1),
    # Multi-caret sequence
    ("1.0^a^b", "1.0^a^c", -1),
    ("1.0^a^c", "1.0^a^b", 1),
    # Mixed separators around operators
    ("1.0+^git1", "1.0^git1", 0),
    ("1.0_^git1", "1.0^git1", 0),
    ("1.0+~rc1", "1.0~rc1", 0),
    ("1.0_~rc1", "1.0~rc1", 0),
]


@pytest.mark.parametrize("label1, label2, expected", VERSION_CASES)
def test_version_cmp_expected(label1, label2, expected):
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
    with patch_rpm:
        result = rpm_lowpkg.version_cmp(label1, label2)
        assert (
            result == expected
        ), f"{label1} vs {label2} => {result}, expected {expected}"


@pytest.mark.parametrize("label1, label2, _", VERSION_CASES)
@pytest.mark.skipif(not HAS_RPM, reason="python rpm module not available")
def test_version_cmp_matches_rpm(label1, label2, _):
    evr1 = _parse_label(label1)
    evr2 = _parse_label(label2)
    py_result = rpm_lowpkg.version_cmp(label1, label2)
    rpm_result = rpm.labelCompare(evr1, evr2)
    assert py_result == rpm_result, (
        f"Mismatch for {label1} vs {label2}: "
        f"pure-Python={py_result}, rpm={rpm_result}"
    )


def test_symmetry_and_transitivity():
    # Small chain that exercises epoch, version, and release ordering properties
    chain = [
        "0:1.0-1",
        "0:1.0-2",
        "0:1.0^git1-1",
        "0:1.0.1-1",
        "1:0.1-1",
    ]
    # Check reflexivity and antisymmetry
    for a in chain:
        assert rpm_lowpkg.version_cmp(a, a) == 0
    # Check ordering across the chain is strictly increasing
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        assert rpm_lowpkg.version_cmp(a, b) < 0
        assert rpm_lowpkg.version_cmp(b, a) > 0


# ===== Optional fuzzing =====
@pytest.mark.skipif(not HAS_RPM, reason="python rpm module not available")
def test_fuzz_against_rpm():
    """
    Deterministic fuzz over a restricted alphabet to spot regressions against rpm.labelCompare().
    """
    rng = random.Random(1337)
    alpha = string.ascii_lowercase
    digits = string.digits
    seps = "._+"
    ops = "~^"

    # Limit length to keep the space sane for CI
    def rand_token():
        t = []
        for _ in range(rng.randint(1, 6)):
            choice = rng.random()
            if choice < 0.55:
                t.append(rng.choice(digits))
            elif choice < 0.85:
                t.append(rng.choice(alpha))
            elif choice < 0.95:
                t.append(rng.choice(seps))
            else:
                t.append(rng.choice(ops))
        return "".join(t).strip("._+")

    def rand_evr():
        # 30% chance epoch, 70% none
        epoch = str(rng.randint(0, 3)) if rng.random() < 0.3 else None
        version = rand_token() or "1"
        release = rand_token() if rng.random() < 0.6 else None
        return (epoch, version, release)

    for _ in range(2000):
        evr1 = rand_evr()
        evr2 = rand_evr()
        l1 = (
            ("" if evr1[0] is None else f"{evr1[0]}:")
            + evr1[1]
            + ("" if evr1[2] is None else f"-{evr1[2]}")
        )
        l2 = (
            ("" if evr2[0] is None else f"{evr2[0]}:")
            + evr2[1]
            + ("" if evr2[2] is None else f"-{evr2[2]}")
        )
        py = rpm_lowpkg.version_cmp(l1, l2)
        rp = rpm.labelCompare(evr1, evr2)
        if py < 0:
            assert rp < 0, (l1, l2, evr1, evr2, py, rp)
        elif py > 0:
            assert rp > 0, (l1, l2, evr1, evr2, py, rp)
        else:
            assert rp == 0, (l1, l2, evr1, evr2, py, rp)


@pytest.mark.skip_on_windows
def test_info():
    """
    Confirm that a nonzero retcode does not raise an exception.
    """
    rpm_out = textwrap.dedent(
        """\
        name: bash
        relocations: (not relocatable)
        version: 4.4.19
        vendor: CentOS
        release: 10.el8
        build_date_time_t: 1573230816
        build_date: 1573230816
        install_date_time_t: 1578952147
        install_date: 1578952147
        build_host: x86-01.mbox.centos.org
        group: Unspecified
        source_rpm: bash-4.4.19-10.el8.src.rpm
        size: 6930068
        arch: x86_64
        license: GPLv3+
        signature: RSA/SHA256, Wed Dec  4 22:45:04 2019, Key ID 05b555b38483c65d
        packager: CentOS Buildsys <bugs@centos.org>
        url: https://www.gnu.org/software/bash
        summary: The GNU Bourne Again shell
        edition: 4.4.19-10.el8
        description:
        The GNU Bourne Again shell (Bash) is a shell or command language
        interpreter that is compatible with the Bourne shell (sh). Bash
        incorporates useful features from the Korn shell (ksh) and the C shell
        (csh). Most sh scripts can be run by bash without modification.
        -----"""
    )
    dunder_salt = {
        "cmd.run_stdout": MagicMock(return_value="LONGSIZE"),
        "cmd.run_all": MagicMock(
            return_value={
                "retcode": 123,
                "stdout": rpm_out,
                "stderr": "",
                "pid": 12345,
            }
        ),
    }
    expected = {
        "bash": {
            "relocations": "(not relocatable)",
            "version": "4.4.19",
            "vendor": "CentOS",
            "release": "10.el8",
            "build_date_time_t": 1573230816,
            "build_date": "2019-11-08T16:33:36Z",
            "install_date_time_t": 1578952147,
            "install_date": "2020-01-13T21:49:07Z",
            "build_host": "x86-01.mbox.centos.org",
            "group": "Unspecified",
            "source_rpm": "bash-4.4.19-10.el8.src.rpm",
            "size": "6930068",
            "arch": "x86_64",
            "license": "GPLv3+",
            "signature": "RSA/SHA256, Wed Dec  4 22:45:04 2019, Key ID 05b555b38483c65d",
            "packager": "CentOS Buildsys <bugs@centos.org>",
            "url": "https://www.gnu.org/software/bash",
            "summary": "The GNU Bourne Again shell",
            "description": "The GNU Bourne Again shell (Bash) is a shell or command language\ninterpreter that is compatible with the Bourne shell (sh). Bash\nincorporates useful features from the Korn shell (ksh) and the C shell\n(csh). Most sh scripts can be run by bash without modification.",
        }
    }
    with patch.dict(rpm_lowpkg.__salt__, dunder_salt):
        result = rpm_lowpkg.info("bash")
        assert result == expected, result
