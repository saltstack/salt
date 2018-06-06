# coding=utf-8
'''
Test case for utils/__init__.py
'''
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

try:
    import pytest
except ImportError:
    pytest = None
import salt.utils


@skipIf(pytest is None, 'PyTest is missing')
class UtilsTestCase(TestCase):
    '''
    Test case for utils/__init__.py
    '''
    def test_get_module_environment(self):
        '''
        Test for salt.utils.get_module_environment
        :return:
        '''
        _globals = {}
        salt.utils.get_module_environment(_globals)
