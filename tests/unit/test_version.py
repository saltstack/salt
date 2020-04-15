# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.version_test
    ~~~~~~~~~~~~~~~~~~~~~~~

    Test salt's regex git describe version parsing
"""

# Import python libs
from __future__ import absolute_import

import re

import salt.version

# Import Salt libs
from salt.version import SaltStackVersion, versions_report
from tests.support.mock import MagicMock, patch

# Import Salt Testing libs
from tests.support.unit import TestCase


class VersionTestCase(TestCase):
    def test_version_parsing(self):
        strip_initial_non_numbers_regex = re.compile(r"(?:[^\d]+)?(?P<vs>.*)")
        expect = (
            ("v0.12.0-19-g767d4f9", (0, 12, 0, 0, "", 0, 19, "g767d4f9"), None),
            ("v0.12.0-85-g2880105", (0, 12, 0, 0, "", 0, 85, "g2880105"), None),
            (
                "debian/0.11.1+ds-1-3-ga0afcbd",
                (0, 11, 1, 0, "", 0, 3, "ga0afcbd"),
                "0.11.1-3-ga0afcbd",
            ),
            ("0.12.1", (0, 12, 1, 0, "", 0, 0, None), None),
            ("0.12.1", (0, 12, 1, 0, "", 0, 0, None), None),
            ("0.17.0rc1", (0, 17, 0, 0, "rc", 1, 0, None), None),
            ("v0.17.0rc1-1-g52ebdfd", (0, 17, 0, 0, "rc", 1, 1, "g52ebdfd"), None),
            ("v2014.1.4.1", (2014, 1, 4, 1, "", 0, 0, None), None),
            (
                "v2014.1.4.1rc3-n/a-abcdefff",
                (2014, 1, 4, 1, "rc", 3, -1, "abcdefff"),
                None,
            ),
            ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0, None), None),
            ("v3000", (3000, "", 0, 0, None), "3000"),
            ("v3000.0", (3000, "", 0, 0, None), "3000"),
            ("v4518.1", (4518, 1, "", 0, 0, None), "4518.1"),
            ("v3000rc1", (3000, "rc", 1, 0, None), "3000rc1"),
            ("v3000rc1-n/a-abcdefff", (3000, "rc", 1, -1, "abcdefff"), None),
            ("3000-n/a-1e7bc8f", (3000, "", 0, -1, "1e7bc8f"), None),
            ("3000.1-n/a-1e7bc8f", (3000, 1, "", 0, -1, "1e7bc8f"), None),
        )

        for vstr, full_info, version in expect:
            saltstack_version = SaltStackVersion.parse(vstr)
            self.assertEqual(saltstack_version.full_info, full_info)
            if version is None:
                version = strip_initial_non_numbers_regex.search(vstr).group("vs")
            self.assertEqual(saltstack_version.string, version)

    def test_version_comparison(self):
        examples = (
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
        )
        for higher_version, lower_version in examples:
            self.assertTrue(SaltStackVersion.parse(higher_version) > lower_version)
            self.assertTrue(SaltStackVersion.parse(lower_version) < higher_version)
            assert SaltStackVersion.parse(lower_version) != higher_version

    def test_unparsable_version(self):
        with self.assertRaises(ValueError):
            SaltStackVersion.from_name("Drunk")

        with self.assertRaises(ValueError):
            SaltStackVersion.parse("Drunk")

    def test_sha(self):
        """
        test matching sha's
        """
        exp_ret = (
            ("d6cd1e2bd19e03a81132a23b2025920577f84e37", True),
            ("2880105", True),
            ("v3000.0.1", False),
            ("v0.12.0-85-g2880105", False),
        )
        for commit, exp in exp_ret:
            ret = SaltStackVersion.git_sha_regex.match(commit)
            if exp:
                assert ret
            else:
                assert not ret

    def test_version_report_lines(self):
        """
        Validate padding in versions report is correct
        """
        # Get a set of all version report name lenghts including padding
        line_lengths = set(
            [
                len(line.split(":")[0])
                for line in list(versions_report())[4:]
                if line != " " and line != "System Versions:"
            ]
        )
        # Check that they are all the same size (only one element in the set)
        assert len(line_lengths) == 1

    def test_string_new_version(self):
        """
        Validate string property method
        using new versioning scheme
        """
        maj_ver = "3000"
        ver = SaltStackVersion(major=maj_ver)
        assert not ver.minor
        assert not ver.bugfix
        assert maj_ver == ver.string

    def test_string_new_version_minor(self):
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
        assert ver.string == "{0}.{1}".format(maj_ver, min_ver)

    def test_string_new_version_minor_as_string(self):
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
        assert ver.string == "{0}.{1}".format(maj_ver, min_ver)

        # This only seems to happen on a cloned repo without its tags
        maj_ver = "3000"
        min_ver = ""
        ver = SaltStackVersion(major=maj_ver, minor=min_ver)
        assert ver.minor is None, "{!r} is not {!r}".format(ver.minor, min_ver)
        assert not ver.bugfix
        assert ver.string == maj_ver

    def test_string_old_version(self):
        """
        Validate string property method
        using old versioning scheme alongside
        minor version
        """
        maj_ver = "2019"
        min_ver = "2"
        ver = SaltStackVersion(major=maj_ver, minor=min_ver)
        assert ver.bugfix == 0
        assert ver.string == "{0}.{1}.0".format(maj_ver, min_ver)

    def test_noc_info(self):
        """
        Test noc_info property method
        """
        expect = (
            ("v2014.1.4.1rc3-n/a-abcdefff", (2014, 1, 4, 1, "rc", 3, -1)),
            ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0)),
            ("v3000", (3000, "", 0, 0)),
            ("v3000.0", (3000, "", 0, 0)),
            ("v4518.1", (4518, 1, "", 0, 0)),
            ("v3000rc1", (3000, "rc", 1, 0)),
            ("v3000rc1-n/a-abcdefff", (3000, "rc", 1, -1)),
        )

        for vstr, noc_info in expect:
            saltstack_version = SaltStackVersion.parse(vstr)
            assert saltstack_version.noc_info, noc_info
            assert len(saltstack_version.noc_info) == len(noc_info)

    def test_full_info(self):
        """
        Test full_Info property method
        """
        expect = (
            ("v2014.1.4.1rc3-n/a-abcdefff", (2014, 1, 4, 1, "rc", 3, -1, "abcdefff")),
            ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0, None)),
            ("v3000", (3000, "", 0, 0, None)),
            ("v3000.0", (3000, "", 0, 0, None)),
            ("v4518.1", (4518, 1, "", 0, 0, None)),
            ("v3000rc1", (3000, "rc", 1, 0, None)),
            ("v3000rc1-n/a-abcdefff", (3000, "rc", 1, -1, "abcdefff")),
        )

        for vstr, full_info in expect:
            saltstack_version = SaltStackVersion.parse(vstr)
            assert saltstack_version.full_info, full_info
            assert len(saltstack_version.full_info) == len(full_info)

    def test_full_info_all_versions(self):
        """
        Test full_info_all_versions property method
        """
        expect = (
            ("v2014.1.4.1rc3-n/a-abcdefff", (2014, 1, 4, 1, "rc", 3, -1, "abcdefff")),
            ("v3.4.1.1", (3, 4, 1, 1, "", 0, 0, None)),
            ("v3000", (3000, None, None, 0, "", 0, 0, None)),
            ("v3000.0", (3000, 0, None, 0, "", 0, 0, None)),
            ("v4518.1", (4518, 1, None, 0, "", 0, 0, None)),
            ("v3000rc1", (3000, None, None, 0, "rc", 2, 0, None)),
            ("v3000rc1-n/a-abcdefff", (3000, None, None, 0, "rc", 1, -1, "abcdefff")),
        )

        for vstr, full_info in expect:
            saltstack_version = SaltStackVersion.parse(vstr)
            assert saltstack_version.full_info_all_versions, full_info
            assert len(saltstack_version.full_info_all_versions) == len(full_info)

    def test_discover_version(self):
        """
        Test call to __discover_version
        when using different versions
        """
        version = {
            ("3000", None): {
                (b"v3000.0rc2-12-g44fe283a77\n", "3000rc2-12-g44fe283a77"),
                (b"v3000", "3000"),
                (b"1234567", "3000-n/a-1234567"),
            },
            (2019, 2): {
                (b"v2019.2.0rc2-12-g44fe283a77\n", "2019.2.0rc2-12-g44fe283a77"),
                (b"v2019.2.0", "2019.2.0"),
                (b"afc9830198dj", "2019.2.0-n/a-afc9830198dj"),
            },
        }
        for maj_min, test_v in version.items():
            for tag_ver, exp in version[maj_min]:
                salt_ver = SaltStackVersion(
                    major=maj_min[0], minor=maj_min[1], bugfix=None
                )
                attrs = {
                    "communicate.return_value": (tag_ver, b""),
                    "returncode.return_value": 0,
                }
                proc_ret = MagicMock(**attrs)
                proc_mock = patch("subprocess.Popen", return_value=proc_ret)
                patch_os = patch("os.path.exists", return_value=True)

                with proc_mock, patch_os:
                    ret = getattr(salt.version, "__discover_version")(salt_ver)
                assert ret == exp

    def test_info_new_version(self):
        """
        test info property method with new versioning scheme
        """
        vers = ((3000, None, None), (3000, 1, None), (3001, 0, None))
        for maj_ver, min_ver, bug_fix in vers:
            ver = SaltStackVersion(major=maj_ver, minor=min_ver, bugfix=bug_fix)
            if min_ver:
                assert ver.info == (maj_ver, min_ver)
            else:
                assert ver.info == (maj_ver,)

    def test_info_old_version(self):
        """
        test info property method with old versioning scheme
        """
        vers = ((2019, 2, 1), (2018, 3, 0), (2017, 7, None))
        for maj_ver, min_ver, bug_fix in vers:
            ver = SaltStackVersion(major=maj_ver, minor=min_ver, bugfix=bug_fix)
            if bug_fix is None:
                assert ver.info == (maj_ver, min_ver, 0, 0)
            else:
                assert ver.info == (maj_ver, min_ver, bug_fix, 0)

    def test_bugfix_string(self):
        """
        test when bugfix is an empty string
        """
        ret = SaltStackVersion(3000, 1, "", 0, 0, None)
        assert ret.info == (3000, 1)
        assert ret.minor == 1
        assert ret.bugfix is None

    def test_version_repr(self):
        """
        Test SaltStackVersion repr for both date
        and new versioning scheme
        """
        expect = (
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
        )

        for ver, repr_ret in expect:
            assert repr(SaltStackVersion(*ver)) == repr_ret
