"""
    tests.integration.shell.master_tops
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import pytest

from tests.support.case import ShellCase


@pytest.mark.windows_whitelisted
class MasterTopsTest(ShellCase):

    _call_binary_ = "salt"

    @pytest.mark.slow_test
    def test_custom_tops_gets_utilized(self):
        resp = self.run_call("state.show_top")
        self.assertTrue(any("master_tops_test" in _x for _x in resp))
