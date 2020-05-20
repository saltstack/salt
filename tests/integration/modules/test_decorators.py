# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import slowTest


@pytest.mark.windows_whitelisted
class DecoratorTest(ModuleCase):
    @slowTest
    def test_module(self):
        self.assertTrue(self.run_function("runtests_decorators.working_function"))

    @slowTest
    def test_depends(self):
        ret = self.run_function("runtests_decorators.depends")
        self.assertTrue(isinstance(ret, dict))
        self.assertTrue(ret["ret"])
        self.assertTrue(isinstance(ret["time"], float))

    @slowTest
    def test_missing_depends(self):
        self.assertEqual(
            {
                "runtests_decorators.missing_depends_will_fallback": None,
                "runtests_decorators.missing_depends": "'runtests_decorators.missing_depends' is not available.",
            },
            self.run_function("runtests_decorators.missing_depends"),
        )

    @slowTest
    def test_bool_depends(self):
        # test True
        self.assertTrue(self.run_function("runtests_decorators.booldependsTrue"))

        # test False
        self.assertIn(
            "is not available",
            self.run_function("runtests_decorators.booldependsFalse"),
        )

    @slowTest
    def test_depends_will_not_fallback(self):
        ret = self.run_function("runtests_decorators.depends_will_not_fallback")
        self.assertTrue(isinstance(ret, dict))
        self.assertTrue(ret["ret"])
        self.assertTrue(isinstance(ret["time"], float))

    @slowTest
    def test_missing_depends_will_fallback(self):
        self.assertListEqual(
            [False, "fallback"],
            self.run_function("runtests_decorators.missing_depends_will_fallback"),
        )

    @slowTest
    def test_command_success_retcode(self):
        ret = self.run_function("runtests_decorators.command_success_retcode")
        self.assertIs(ret, True)

    @slowTest
    def test_command_failure_retcode(self):
        ret = self.run_function("runtests_decorators.command_failure_retcode")
        self.assertEqual(
            ret, "'runtests_decorators.command_failure_retcode' is not available."
        )

    @slowTest
    def test_command_success_nonzero_retcode_true(self):
        ret = self.run_function(
            "runtests_decorators.command_success_nonzero_retcode_true"
        )
        self.assertIs(ret, True)

    @slowTest
    def test_command_failure_nonzero_retcode_true(self):
        ret = self.run_function(
            "runtests_decorators.command_failure_nonzero_retcode_true"
        )
        self.assertEqual(
            ret,
            "'runtests_decorators.command_failure_nonzero_retcode_true' is not available.",
        )

    @slowTest
    def test_command_success_nonzero_retcode_false(self):
        ret = self.run_function(
            "runtests_decorators.command_success_nonzero_retcode_false"
        )
        self.assertIs(ret, True)

    @slowTest
    def test_command_failure_nonzero_retcode_false(self):
        ret = self.run_function(
            "runtests_decorators.command_failure_nonzero_retcode_false"
        )
        self.assertEqual(
            ret,
            "'runtests_decorators.command_failure_nonzero_retcode_false' is not available.",
        )

    @slowTest
    def test_versioned_depend_insufficient(self):
        self.assertIn(
            "is not available",
            self.run_function("runtests_decorators.version_depends_false"),
        )

    @slowTest
    def test_versioned_depend_sufficient(self):
        self.assertTrue(self.run_function("runtests_decorators.version_depends_true"))

    @slowTest
    def test_versioned_depend_versionless(self):
        self.assertTrue(
            self.run_function("runtests_decorators.version_depends_versionless_true")
        )
