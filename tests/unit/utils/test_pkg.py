# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals, print_function

from tests.support.unit import TestCase, skipIf
from tests.support.mock import Mock, MagicMock, patch, NO_MOCK, NO_MOCK_REASON
import salt.utils.pkg
from salt.utils.pkg import rpm

try:
    import pytest
except ImportError:
    pytest = None


class PkgUtilsTestCase(TestCase):
    '''
    TestCase for salt.utils.pkg module
    '''
    test_parameters = [
        ("16.0.0.49153-0+f1", "", "16.0.0.49153-0+f1"),
        ("> 15.0.0", ">", "15.0.0"),
        ("< 15.0.0", "<", "15.0.0"),
        ("<< 15.0.0", "<<", "15.0.0"),
        (">> 15.0.0", ">>", "15.0.0"),
        (">= 15.0.0", ">=", "15.0.0"),
        ("<= 15.0.0", "<=", "15.0.0"),
        ("!= 15.0.0", "!=", "15.0.0"),
        ("<=> 15.0.0", "<=>", "15.0.0"),
        ("<> 15.0.0", "<>", "15.0.0"),
        ("= 15.0.0", "=", "15.0.0"),
        (">15.0.0", ">", "15.0.0"),
        ("<15.0.0", "<", "15.0.0"),
        ("<<15.0.0", "<<", "15.0.0"),
        (">>15.0.0", ">>", "15.0.0"),
        (">=15.0.0", ">=", "15.0.0"),
        ("<=15.0.0", "<=", "15.0.0"),
        ("!=15.0.0", "!=", "15.0.0"),
        ("<=>15.0.0", "<=>", "15.0.0"),
        ("<>15.0.0", "<>", "15.0.0"),
        ("=15.0.0", "=", "15.0.0"),
        ("", "", "")
    ]

    def test_split_comparison(self):
        '''
        Tests salt.utils.pkg.split_comparison
        '''
        for test_parameter in self.test_parameters:
            oper, verstr = salt.utils.pkg.split_comparison(test_parameter[0])
            self.assertEqual(test_parameter[1], oper)
            self.assertEqual(test_parameter[2], verstr)
