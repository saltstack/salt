"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest
import yaml

import salt.modules.pkg_resource as pkg_resource
import salt.utils.data
import salt.utils.yaml
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pkg_resource: {}}


def test_pack_sources():
    """
    Test to accepts list of dicts (or a string representing a
    list of dicts) and packs the key/value pairs into a single dict.
    """
    with patch.object(
        salt.utils.yaml,
        "safe_load",
        MagicMock(side_effect=yaml.parser.ParserError("f")),
    ):
        with patch.dict(pkg_resource.__salt__, {"pkg.normalize_name": MagicMock()}):
            assert pkg_resource.pack_sources("sources") == {}

            assert pkg_resource.pack_sources(["A", "a"]) == {}

            assert pkg_resource.pack_sources([{"A": "a"}])


def test_parse_targets():
    """
    Test to parses the input to pkg.install and
    returns back the package(s) to be installed. Returns a
    list of packages, as well as a string noting whether the
    packages are to come from a repository or a binary package.
    """
    with patch.dict(pkg_resource.__grains__, {"os": "A"}):
        assert pkg_resource.parse_targets(pkgs="a", sources="a") == (None, None)

        with patch.object(pkg_resource, "_repack_pkgs", return_value=False):
            assert pkg_resource.parse_targets(pkgs="a") == (None, None)

        with patch.object(pkg_resource, "_repack_pkgs", return_value="A"):
            assert pkg_resource.parse_targets(pkgs="a") == ("A", "repository")

    with patch.dict(pkg_resource.__grains__, {"os": "MacOS1"}):
        with patch.object(pkg_resource, "pack_sources", return_value=False):
            assert pkg_resource.parse_targets(sources="s") == (None, None)

        with patch.object(pkg_resource, "pack_sources", return_value={"A": "/a"}):
            with patch.dict(
                pkg_resource.__salt__,
                {"config.valid_fileproto": MagicMock(return_value=False)},
            ):
                assert pkg_resource.parse_targets(sources="s") == (["/a"], "file")

        with patch.object(pkg_resource, "pack_sources", return_value={"A": "a"}):
            with patch.dict(
                pkg_resource.__salt__,
                {"config.valid_fileproto": MagicMock(return_value=False)},
            ):
                assert pkg_resource.parse_targets(name="n") == (
                    {"n": None},
                    "repository",
                )

                assert pkg_resource.parse_targets() == (None, None)


def test_version():
    """
    Test to Common interface for obtaining the version
    of installed packages.
    """
    with patch.object(salt.utils.data, "is_true", return_value=True):
        mock = MagicMock(return_value={"A": "B"})
        with patch.dict(pkg_resource.__salt__, {"pkg.list_pkgs": mock}):
            assert pkg_resource.version("A") == "B"

            assert pkg_resource.version() == {}

        mock = MagicMock(return_value={})
        with patch.dict(pkg_resource.__salt__, {"pkg.list_pkgs": mock}):
            with patch("builtins.next") as mock_next:
                mock_next.side_effect = StopIteration()
                assert pkg_resource.version("A") == ""


def test_add_pkg():
    """
    Test to add a package to a dict of installed packages.
    """
    assert pkg_resource.add_pkg({"pkgs": []}, "name", "version") is None


def test_sort_pkglist():
    """
    Test to accepts a dict obtained from pkg.list_pkgs() and sorts
    in place the list of versions for any packages that have multiple
    versions installed, so that two package lists can be compared
    to one another.
    """
    assert pkg_resource.sort_pkglist({}) is None


def test_format_pkg_list_no_attr():
    """
    Test to output format of the package list with no attr parameter.
    """
    packages = {
        "glibc": [
            {
                "version": "2.12",
                "epoch": None,
                "release": "1.212.el6",
                "arch": "x86_64",
            }
        ],
        "glibc.i686": [
            {
                "version": "2.12",
                "epoch": None,
                "release": "1.212.el6",
                "arch": "i686",
            }
        ],
        "foobar": [
            {"version": "1.2.0", "epoch": "2", "release": "7", "arch": "x86_64"},
            {"version": "1.2.3", "epoch": "2", "release": "27", "arch": "x86_64"},
        ],
        "foobar.something": [
            {"version": "1.1", "epoch": "3", "release": "23.1", "arch": "i686"}
        ],
        "foobar.": [
            {"version": "1.1", "epoch": "3", "release": "23.1", "arch": "i686"}
        ],
    }
    expected_pkg_list = {
        "glibc": "2.12-1.212.el6",
        "glibc.i686": "2.12-1.212.el6",
        "foobar": "2:1.2.0-7,2:1.2.3-27",
        "foobar.something": "3:1.1-23.1",
        "foobar.": "3:1.1-23.1",
    }
    assert pkg_resource.format_pkg_list(packages, False, None) == expected_pkg_list


def test_format_pkg_list_with_attr():
    """
    Test to output format of the package list with attr parameter.
    In this case, any redundant "arch" reference will be removed
    from the package name since it's included as part of the requested attr.
    """
    name_arch_mapping = {
        "glibc": {"name": "glibc", "arch": None},
        "glibc.i686": {"name": "glibc", "arch": "i686"},
        "foobar": {"name": "foobar", "arch": None},
        "foobar.something": {"name": "foobar.something", "arch": None},
        "foobar.": {"name": "foobar.", "arch": None},
    }
    packages = {
        "glibc": [
            {
                "version": "2.12",
                "epoch": None,
                "release": "1.212.el6",
                "arch": "x86_64",
            }
        ],
        "glibc.i686": [
            {
                "version": "2.12",
                "epoch": None,
                "release": "1.212.el6",
                "arch": "i686",
            }
        ],
        "foobar": [
            {"version": "1.2.0", "epoch": "2", "release": "7", "arch": "x86_64"},
            {"version": "1.2.3", "epoch": "2", "release": "27", "arch": "x86_64"},
        ],
        "foobar.something": [
            {"version": "1.1", "epoch": "3", "release": "23.1", "arch": "i686"}
        ],
        "foobar.": [
            {"version": "1.1", "epoch": "3", "release": "23.1", "arch": "i686"}
        ],
    }
    expected_pkg_list = {
        "glibc": [
            {
                "arch": "x86_64",
                "release": "1.212.el6",
                "epoch": None,
                "version": "2.12",
            },
            {
                "arch": "i686",
                "release": "1.212.el6",
                "epoch": None,
                "version": "2.12",
            },
        ],
        "foobar": [
            {"arch": "x86_64", "release": "7", "epoch": "2", "version": "1.2.0"},
            {"arch": "x86_64", "release": "27", "epoch": "2", "version": "1.2.3"},
        ],
        "foobar.": [
            {"arch": "i686", "release": "23.1", "epoch": "3", "version": "1.1"}
        ],
        "foobar.something": [
            {"arch": "i686", "release": "23.1", "epoch": "3", "version": "1.1"}
        ],
    }
    with patch.dict(pkg_resource.__salt__, {"pkg.parse_arch": name_arch_mapping.get}):
        pkgs = pkg_resource.format_pkg_list(packages, False, attr=["epoch", "release"])
        assert sorted(pkgs) == sorted(expected_pkg_list)


def test_repack_pkgs():
    """
    Test to check that repack function is raising error in case of
    package name collisions
    """
    assert pkg_resource._repack_pkgs([{"A": "a"}])
    assert pkg_resource._repack_pkgs([{"A": "a"}, {"B": "b"}])
    with pytest.raises(SaltInvocationError):
        assert pkg_resource._repack_pkgs([{"A": "a"}, {"A": "c"}])


def test_stringify():
    """
    Test to takes a dict of package name/version information
    and joins each list of
    installed versions into a string.
    """
    assert pkg_resource.stringify({}) is None


def test_version_clean():
    """
    Test to clean the version string removing extra data.
    """
    with patch.dict(
        pkg_resource.__salt__, {"pkg.version_clean": MagicMock(return_value="A")}
    ):
        assert pkg_resource.version_clean("version") == "A"

    assert pkg_resource.version_clean("v") == "v"


def test_check_extra_requirements():
    """
    Test to check if the installed package already
    has the given requirements.
    """
    with patch.dict(
        pkg_resource.__salt__,
        {"pkg.check_extra_requirements": MagicMock(return_value="A")},
    ):
        assert pkg_resource.check_extra_requirements("a", "b") == "A"

    assert pkg_resource.check_extra_requirements("a", False)


def test_version_compare():
    """
    Test the version_compare function

    TODO: Come up with a good way to test epoch handling across different
    platforms. This function will look in the ``__salt__`` dunder for a
    version_cmp function (which not all pkg modules implement) and use that
    to perform platform-specific handling (including interpretation of
    epochs), but even an integration test would need to take into account
    the fact that not all package managers grok epochs.
    """
    assert pkg_resource.version_compare("2.0", "<", "3.0") is True
