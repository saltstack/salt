# coding=utf-8
'''
Test case for utils/__init__.py
'''
from __future__ import unicode_literals, print_function, absolute_import
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
    def test_get_module_environment_empty(self):
        '''
        Test for salt.utils.get_module_environment
        Test if empty globals returns to an empty environment
        with the correct type.
        :return:
        '''
        out = salt.utils.get_module_environment({})
        assert out == {}
        assert isinstance(out, dict)

    def test_get_module_environment_opts(self):
        '''
        Test for salt.utils.get_module_environment

        :return:
        '''
        expectation = {'message': 'Melting hard drives'}
        _globals = {'__opts__': {'system-environment': {'salt.in.system': expectation}},
                    '__file__': '/daemons/loose/in/system.py'}
        assert salt.utils.get_module_environment(_globals) == expectation
