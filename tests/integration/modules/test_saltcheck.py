# -*- coding: utf-8 -*-
"""
Test the saltcheck module
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase


class SaltcheckModuleTest(ModuleCase):
    """
    Test the saltcheck module
    """

    def test_saltcheck_run(self):
        """
        saltcheck.run_test
        """
        saltcheck_test = {
            "module_and_function": "test.echo",
            "assertion": "assertEqual",
            "expected_return": "This works!",
            "args": ["This works!"],
        }
        ret = self.run_function("saltcheck.run_test", test=saltcheck_test)
        self.assertDictContainsSubset({"status": "Pass"}, ret)

    def test_saltcheck_state(self):
        """
        saltcheck.run_state_tests
        """
        saltcheck_test = "validate-saltcheck"
        ret = self.run_function("saltcheck.run_state_tests", [saltcheck_test])
        self.assertDictContainsSubset(
            {"status": "Pass"}, ret[0]["validate-saltcheck"]["echo_test_hello"]
        )

    def test_topfile_validation(self):
        """
        saltcheck.run_highstate_tests
        """
        expected_top_states = self.run_function("state.show_top").get("base", [])
        expected_top_states.append("TEST RESULTS")
        ret = self.run_function("saltcheck.run_highstate_tests")
        for top_state_dict in ret:
            self.assertIn(list(top_state_dict)[0], expected_top_states)

    def test_saltcheck_checkall(self):
        """
        Validate saltcheck.run_state_tests check_all for the default saltenv of base.
        validate-saltcheck state hosts a saltcheck-tests directory with 2 .tst files. By running
          check_all=True, both files should be found and show passed results.
        """
        saltcheck_test = "validate-saltcheck"
        ret = self.run_function(
            "saltcheck.run_state_tests", [saltcheck_test], check_all=True
        )
        self.assertDictContainsSubset(
            {"status": "Pass"}, ret[0]["validate-saltcheck"]["echo_test_hello"]
        )
        self.assertDictContainsSubset(
            {"status": "Pass"}, ret[0]["validate-saltcheck"]["check_all_validate"]
        )

    def test_saltcheck_checkall_saltenv(self):
        """
        Validate saltcheck.run_state_tests check_all for the prod saltenv
        validate-saltcheck state hosts a saltcheck-tests directory with 2 .tst files. By running
          check_all=True, both files should be found and show passed results.
        """
        saltcheck_test = "validate-saltcheck"
        ret = self.run_function(
            "saltcheck.run_state_tests",
            [saltcheck_test],
            saltenv="prod",
            check_all=True,
        )
        self.assertDictContainsSubset(
            {"status": "Pass"}, ret[0]["validate-saltcheck"]["echo_test_prod_env"]
        )
        self.assertDictContainsSubset(
            {"status": "Pass"}, ret[0]["validate-saltcheck"]["check_all_validate_prod"]
        )
