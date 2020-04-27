# -*- coding: utf-8 -*-
"""
tests for pkgrepo states
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

import salt.utils.files

# Import Salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    requires_salt_modules,
    requires_salt_states,
    requires_system_grains,
)
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf


@destructiveTest
@skipIf(salt.utils.platform.is_windows(), "minion is windows")
class PkgrepoTest(ModuleCase, SaltReturnAssertsMixin):
    """
    pkgrepo state tests
    """

    @requires_salt_modules("pkgrepo.managed")
    @requires_system_grains
    def test_pkgrepo_01_managed(self, grains):
        """
        Test adding a repo
        """
        if grains["os"] == "Ubuntu" and grains["osrelease_info"] >= (15, 10):
            self.skipTest(
                "The PPA used for this test does not exist for Ubuntu Wily"
                " (15.10) and later."
            )

        if grains["os_family"] == "Debian":
            try:
                from aptsources import sourceslist  # pylint: disable=unused-import
            except ImportError:
                self.skipTest("aptsources.sourceslist python module not found")
        ret = self.run_function("state.sls", mods="pkgrepo.managed", timeout=120)
        # If the below assert fails then no states were run, and the SLS in
        # tests/integration/files/file/base/pkgrepo/managed.sls needs to be
        # corrected.
        self.assertReturnNonEmptySaltType(ret)
        for state_id, state_result in six.iteritems(ret):
            self.assertSaltTrueReturn(dict([(state_id, state_result)]))

    @requires_salt_modules("pkgrepo.absent")
    @requires_system_grains
    def test_pkgrepo_02_absent(self, grains):
        """
        Test removing the repo from the above test
        """
        if grains["os"] == "Ubuntu" and grains["osrelease_info"] >= (15, 10):
            self.skipTest(
                "The PPA used for this test does not exist for Ubuntu Wily"
                " (15.10) and later."
            )

        ret = self.run_function("state.sls", mods="pkgrepo.absent", timeout=120)
        # If the below assert fails then no states were run, and the SLS in
        # tests/integration/files/file/base/pkgrepo/absent.sls needs to be
        # corrected.
        self.assertReturnNonEmptySaltType(ret)
        for state_id, state_result in six.iteritems(ret):
            self.assertSaltTrueReturn(dict([(state_id, state_result)]))

    @requires_salt_states("pkgrepo.absent", "pkgrepo.managed")
    @requires_system_grains
    def test_pkgrepo_03_with_comments(self, grains):
        """
        Test adding a repo with comments
        """
        kwargs = {}
        if grains["os_family"] == "RedHat":
            kwargs = {
                "name": "examplerepo",
                "baseurl": "http://example.com/repo",
                "enabled": False,
                "comments": ["This is a comment"],
            }
        else:
            self.skipTest(
                "{}/{} test case needed".format(grains["os_family"], grains["os"])
            )

        try:
            # Run the state to add the repo
            ret = self.run_state("pkgrepo.managed", **kwargs)
            self.assertSaltTrueReturn(ret)

            # Run again with modified comments
            kwargs["comments"].append("This is another comment")
            ret = self.run_state("pkgrepo.managed", **kwargs)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertEqual(
                ret["changes"],
                {
                    "comments": {
                        "old": ["This is a comment"],
                        "new": ["This is a comment", "This is another comment"],
                    }
                },
            )

            # Run a third time, no changes should be made
            ret = self.run_state("pkgrepo.managed", **kwargs)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertFalse(ret["changes"])
            self.assertEqual(
                ret["comment"],
                "Package repo '{0}' already configured".format(kwargs["name"]),
            )
        finally:
            # Clean up
            self.run_state("pkgrepo.absent", name=kwargs["name"])

    @requires_salt_states("pkgrepo.managed")
    @requires_system_grains
    def test_pkgrepo_04_apt_with_architectures(self, grains):
        """
        Test managing a repo with architectures specified
        """
        if grains["os_family"].lower() != "debian":
            self.skipTest("APT-only test")

        name = "deb {{arch}}http://foo.com/bar/latest {oscodename} main".format(
            oscodename=grains["oscodename"]
        )

        def _get_arch(arch):
            return "[arch={0}] ".format(arch) if arch else ""

        def _run(arch="", test=False):
            ret = self.run_state(
                "pkgrepo.managed",
                name=name.format(arch=_get_arch(arch)),
                file=fn_,
                refresh=False,
                test=test,
            )
            return ret[next(iter(ret))]

        fn_ = salt.utils.files.mkstemp(dir="/etc/apt/sources.list.d", suffix=".list")

        try:
            # Run with test=True
            ret = _run(test=True)
            assert ret["changes"] == {"repo": name.format(arch="")}, ret["changes"]
            assert "would be" in ret["comment"], ret["comment"]
            assert ret["result"] is None, ret["result"]

            # Run for real
            ret = _run()
            assert ret["changes"] == {"repo": name.format(arch="")}, ret["changes"]
            assert ret["comment"].startswith("Configured"), ret["comment"]
            assert ret["result"] is True, ret["result"]

            # Run again with test=True, should exit with no changes and a True
            # result.
            ret = _run(test=True)
            assert not ret["changes"], ret["changes"]
            assert "already" in ret["comment"], ret["comment"]
            assert ret["result"] is True, ret["result"]

            # Run for real again, results should be the same as above (i.e. we
            # should never get to the point where we exit with a None result).
            ret = _run()
            assert not ret["changes"], ret["changes"]
            assert "already" in ret["comment"], ret["comment"]
            assert ret["result"] is True, ret["result"]

            expected_changes = {
                "line": {
                    "new": name.format(arch=_get_arch("amd64")),
                    "old": name.format(arch=""),
                },
                "architectures": {"new": ["amd64"], "old": []},
            }

            # Run with test=True and the architecture set. We should get a None
            # result with some expected changes.
            ret = _run(arch="amd64", test=True)
            assert ret["changes"] == expected_changes, ret["changes"]
            assert "would be" in ret["comment"], ret["comment"]
            assert ret["result"] is None, ret["result"]

            # Run for real, with the architecture set. We should get a True
            # result with the same changes.
            ret = _run(arch="amd64")
            assert ret["changes"] == expected_changes, ret["changes"]
            assert ret["comment"].startswith("Configured"), ret["comment"]
            assert ret["result"] is True, ret["result"]

            # Run again with test=True, should exit with no changes and a True
            # result.
            ret = _run(arch="amd64", test=True)
            assert not ret["changes"], ret["changes"]
            assert "already" in ret["comment"], ret["comment"]
            assert ret["result"] is True, ret["result"]

            # Run for real again, results should be the same as above (i.e. we
            # should never get to the point where we exit with a None result).
            ret = _run(arch="amd64")
            assert not ret["changes"], ret["changes"]
            assert "already" in ret["comment"], ret["comment"]
            assert ret["result"] is True, ret["result"]

            expected_changes = {
                "line": {
                    "new": name.format(arch=""),
                    "old": name.format(arch=_get_arch("amd64")),
                },
                "architectures": {"new": [], "old": ["amd64"]},
            }

            # Run with test=True and the architecture set back to the original
            # value. We should get a None result with some expected changes.
            ret = _run(test=True)
            assert ret["changes"] == expected_changes, ret["changes"]
            assert "would be" in ret["comment"], ret["comment"]
            assert ret["result"] is None, ret["result"]

            # Run for real, with the architecture set. We should get a True
            # result with the same changes.
            ret = _run()
            assert ret["changes"] == expected_changes, ret["changes"]
            assert ret["comment"].startswith("Configured"), ret["comment"]
            assert ret["result"] is True, ret["result"]

            # Run again with test=True, should exit with no changes and a True
            # result.
            ret = _run(test=True)
            assert not ret["changes"], ret["changes"]
            assert "already" in ret["comment"], ret["comment"]
            assert ret["result"] is True, ret["result"]

            # Run for real again, results should be the same as above (i.e. we
            # should never get to the point where we exit with a None result).
            ret = _run()
            assert not ret["changes"], ret["changes"]
            assert "already" in ret["comment"], ret["comment"]
            assert ret["result"] is True, ret["result"]
        finally:
            try:
                os.remove(fn_)
            except OSError:
                pass
