"""
tests.integration.states.match
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import os

import pytest
import salt.utils.files
import salt.utils.stringutils
from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS


class StateMatchTest(ModuleCase):
    """
    Validate the file state
    """

    @pytest.mark.slow_test
    @pytest.mark.skip_if_not_root
    def test_issue_2167_ipcidr_no_AttributeError(self):
        subnets = self.run_function("network.subnets")
        self.assertTrue(len(subnets) > 0)
        top_filename = "issue-2167-ipcidr-match.sls"
        top_file = os.path.join(RUNTIME_VARS.BASE_FILES, top_filename)
        try:
            with salt.utils.files.fopen(top_file, "w") as fp_:
                fp_.write(
                    salt.utils.stringutils.to_str(
                        "base:\n"
                        "  {}:\n"
                        "    - match: ipcidr\n"
                        "    - test\n".format(subnets[0])
                    )
                )
            ret = self.run_function("state.top", [top_filename])
            self.assertNotIn(
                "AttributeError: 'Matcher' object has no attribute " "'functions'", ret
            )
        finally:
            os.remove(top_file)
