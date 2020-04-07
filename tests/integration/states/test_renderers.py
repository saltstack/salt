# coding: utf-8
"""
Integration tests for renderer functions
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import flaky
from tests.support.unit import skipIf


class TestJinjaRenderer(ModuleCase):
    """
    Validate that ordering works correctly
    """

    def test_dot_notation(self):
        """
        Test the Jinja dot-notation syntax for calling execution modules
        """
        ret = self.run_function("state.sls", ["jinja_dot_notation"])
        for state_ret in ret.values():
            self.assertTrue(state_ret["result"])

    @flaky
    @skipIf(
        salt.utils.platform.is_darwin() and six.PY2, "This test hangs on OS X on Py2"
    )
    def test_salt_contains_function(self):
        """
        Test if we are able to check if a function exists inside the "salt"
        wrapper (AliasLoader) which is available on Jinja templates.
        """
        ret = self.run_function("state.sls", ["jinja_salt_contains_function"])
        for state_ret in ret.values():
            self.assertTrue(state_ret["result"])
