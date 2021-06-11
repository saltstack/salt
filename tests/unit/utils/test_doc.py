# -*- coding: utf-8 -*-
"""
Unit Tests for functions located in salt.utils.doc.py.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.doc

# Import Salt Testing libs
from tests.support.unit import TestCase


class DocUtilsTestCase(TestCase):
    """
    Test case for doc util.
    """

    def test_parse_docstring(self):
        test_keystone_str = """Management of Keystone users
                                ============================

                                :depends:   - keystoneclient Python module
                                :configuration: See :py:mod:`salt.modules.keystone` for setup instructions.
"""

        ret = salt.utils.doc.parse_docstring(test_keystone_str)
        expected_dict = {
            "deps": ["keystoneclient"],
            "full": "Management of Keystone users\n                                "
            "============================\n\n                                "
            ":depends:   - keystoneclient Python module\n                                "
            ":configuration: See :py:mod:`salt.modules.keystone` for setup instructions.\n",
        }
        self.assertDictEqual(ret, expected_dict)
