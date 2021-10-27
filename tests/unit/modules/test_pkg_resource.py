"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""


import salt.modules.pkg_resource as pkg_resource
import salt.utils.data
import salt.utils.yaml
import yaml
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PkgresTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.pkg_resource
    """

    def setup_loader_modules(self):
        return {pkg_resource: {}}

    def test_pack_sources(self):
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
                self.assertDictEqual(pkg_resource.pack_sources("sources"), {})

                self.assertDictEqual(pkg_resource.pack_sources(["A", "a"]), {})

                self.assertTrue(pkg_resource.pack_sources([{"A": "a"}]))

    def test_parse_targets(self):
        """
        Test to parses the input to pkg.install and
        returns back the package(s) to be installed. Returns a
        list of packages, as well as a string noting whether the
        packages are to come from a repository or a binary package.
        """
        with patch.dict(pkg_resource.__grains__, {"os": "A"}):
            self.assertEqual(
                pkg_resource.parse_targets(pkgs="a", sources="a"), (None, None)
            )

            with patch.object(pkg_resource, "_repack_pkgs", return_value=False):
                self.assertEqual(pkg_resource.parse_targets(pkgs="a"), (None, None))

            with patch.object(pkg_resource, "_repack_pkgs", return_value="A"):
                self.assertEqual(
                    pkg_resource.parse_targets(pkgs="a"), ("A", "repository")
                )

        with patch.dict(pkg_resource.__grains__, {"os": "MacOS1"}):
            with patch.object(pkg_resource, "pack_sources", return_value=False):
                self.assertEqual(pkg_resource.parse_targets(sources="s"), (None, None))

            with patch.object(pkg_resource, "pack_sources", return_value={"A": "/a"}):
                with patch.dict(
                    pkg_resource.__salt__,
                    {"config.valid_fileproto": MagicMock(return_value=False)},
                ):
                    self.assertEqual(
                        pkg_resource.parse_targets(sources="s"), (["/a"], "file")
                    )

            with patch.object(pkg_resource, "pack_sources", return_value={"A": "a"}):
                with patch.dict(
                    pkg_resource.__salt__,
                    {"config.valid_fileproto": MagicMock(return_value=False)},
                ):
                    self.assertEqual(
                        pkg_resource.parse_targets(name="n"),
                        ({"n": None}, "repository"),
                    )

                    self.assertEqual(pkg_resource.parse_targets(), (None, None))

    def test_version(self):
        """
        Test to Common interface for obtaining the version
        of installed packages.
        """
        with patch.object(salt.utils.data, "is_true", return_value=True):
            mock = MagicMock(return_value={"A": "B"})
            with patch.dict(pkg_resource.__salt__, {"pkg.list_pkgs": mock}):
                self.assertEqual(pkg_resource.version("A"), "B")

                self.assertDictEqual(pkg_resource.version(), {})

            mock = MagicMock(return_value={})
            with patch.dict(pkg_resource.__salt__, {"pkg.list_pkgs": mock}):
                with patch("builtins.next") as mock_next:
                    mock_next.side_effect = StopIteration()
                    self.assertEqual(pkg_resource.version("A"), "")

    def test_add_pkg(self):
        """
        Test to add a package to a dict of installed packages.
        """
        self.assertIsNone(pkg_resource.add_pkg({"pkgs": []}, "name", "version"))

    def test_sort_pkglist(self):
        """
        Test to accepts a dict obtained from pkg.list_pkgs() and sorts
        in place the list of versions for any packages that have multiple
        versions installed, so that two package lists can be compared
        to one another.
        """
        self.assertIsNone(pkg_resource.sort_pkglist({}))

    def test_format_pkg_list_no_attr(self):
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
        self.assertCountEqual(
            pkg_resource.format_pkg_list(packages, False, None), expected_pkg_list
        )

    def test_format_pkg_list_with_attr(self):
        """
        Test to output format of the package list with attr parameter.
        In this case, any redundant "arch" reference will be removed from the package name since it's
        include as part of the requested attr.
        """
        NAME_ARCH_MAPPING = {
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
        with patch.dict(
            pkg_resource.__salt__, {"pkg.parse_arch": NAME_ARCH_MAPPING.get}
        ):
            self.assertCountEqual(
                pkg_resource.format_pkg_list(
                    packages, False, attr=["epoch", "release"]
                ),
                expected_pkg_list,
            )

    def test_stringify(self):
        """
        Test to takes a dict of package name/version information
        and joins each list of
        installed versions into a string.
        """
        self.assertIsNone(pkg_resource.stringify({}))

    def test_version_clean(self):
        """
        Test to clean the version string removing extra data.
        """
        with patch.dict(
            pkg_resource.__salt__, {"pkg.version_clean": MagicMock(return_value="A")}
        ):
            self.assertEqual(pkg_resource.version_clean("version"), "A")

        self.assertEqual(pkg_resource.version_clean("v"), "v")

    def test_check_extra_requirements(self):
        """
        Test to check if the installed package already
        has the given requirements.
        """
        with patch.dict(
            pkg_resource.__salt__,
            {"pkg.check_extra_requirements": MagicMock(return_value="A")},
        ):
            self.assertEqual(pkg_resource.check_extra_requirements("a", "b"), "A")

        self.assertTrue(pkg_resource.check_extra_requirements("a", False))

    def test_version_compare(self):
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
