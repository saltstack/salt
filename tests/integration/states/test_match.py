"""
tests.integration.states.match
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import pytest

from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS


class StateMatchTest(ModuleCase):
    """
    Validate the file state
    """

    @pytest.mark.slow_test
    def test_issue_2167_ipcidr_no_AttributeError(self):
        subnets = self.run_function("network.subnets")
        self.assertTrue(len(subnets) > 0)
        sls_contents = """
        base:
          {}:
            - match: ipcidr
            - test
        """.format(
            subnets[0]
        )
        top_filename = "issue-2167-ipcidr-match.sls"
        with pytest.helpers.temp_file(
            top_filename, sls_contents, RUNTIME_VARS.TMP_BASEENV_STATE_TREE
        ):
            ret = self.run_function("state.top", [top_filename])
            self.assertNotIn(
                "AttributeError: 'Matcher' object has no attribute 'functions'", ret
            )
