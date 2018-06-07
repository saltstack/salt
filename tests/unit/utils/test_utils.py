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
        Test if __opts__ are visible.
        :return:
        '''
        expectation = {'message': 'Melting hard drives'}
        _globals = {'__opts__': {'system-environment': {
            'salt.in.system': expectation}},
                    '__file__': '/daemons/loose/in/system.py'}
        assert salt.utils.get_module_environment(_globals) == expectation

    def test_get_module_environment_pillars(self):
        '''
        Test for salt.utils.get_module_environment
        Test if __pillar__ is visible.
        :return:
        '''
        expectation = {'message': 'The CPU has shifted, and become decentralized.'}
        _globals = {'__pillar__': {'system-environment': {
            'salt.electric.interference': expectation}},
                    '__file__': '/piezo/electric/interference.py'}
        assert salt.utils.get_module_environment(_globals) == expectation

    def test_get_module_environment_pillar_override(self):
        '''
        Test for salt.utils.get_module_environment
        Test if __pillar__ is overriding __opts__.
        :return:
        '''
        expectation = {'msg': 'The CPU has shifted, and become decentralized.'}
        _globals = {
            '__pillar__': {'system-environment': {'salt.electric.interference': expectation}},
            '__opts__': {'system-environment': {'salt.electric.interference': {'msg': 'la!'}}},
            '__file__': '/piezo/electric/interference.py'
        }
        assert salt.utils.get_module_environment(_globals) == expectation

    def test_get_module_environment_sname_found(self):
        '''
        Test for salt.utils.get_module_environment
        Section name and module name are found.
        :return:
        '''
        expectation = {'msg': 'All operators are on strike due to broken coffee machine!'}
        _globals = {
            '__pillar__': {'system-environment': {'salt.jumping.interference': expectation}},
            '__file__': '/route/flapping/at_the_nap.py'
        }
        assert salt.utils.get_module_environment(_globals) == {}

        _globals['__file__'] = '/route/jumping/interference.py'
        assert salt.utils.get_module_environment(_globals) == expectation

    def test_get_module_environment_mname_found(self):
        '''
        Test for salt.utils.get_module_environment
        Module name is found.

        :return:
        '''
        expectation = {'msg': 'All operators are on strike due to broken coffee machine!'}
        _globals = {
            '__pillar__': {'system-environment': {'salt.jumping.nonsense': expectation}},
            '__file__': '/route/jumping/interference.py'
        }
        assert salt.utils.get_module_environment(_globals) == {}
        _globals['__pillar__']['system-environment']['salt.jumping.interference'] = expectation
        assert salt.utils.get_module_environment(_globals) == expectation

    def test_get_module_environment_vname_found(self):
        '''
        Test for salt.utils.get_module_environment
        Virtual name is found.

        :return:
        '''
        expectation = {'msg': 'All operators are on strike due to broken coffee machine!'}
        _globals = {
            '__pillar__': {'system-environment': {'salt.jumping.nonsense': expectation}},
            '__virtualname__': 'nonsense',
            '__file__': '/lost/in/jumping/translation.py'
        }
        assert salt.utils.get_module_environment(_globals) == expectation

    def test_get_module_environment_vname_overridden(self):
        '''
        Test for salt.utils.get_module_environment
        Virtual namespace overridden.

        :return:
        '''
        expectation = {'msg': 'New management.'}
        _globals = {
            '__pillar__': {'system-environment': {'salt.funny.nonsense': {'msg': 'This is wrong'},
                                                  'salt.funny.translation': expectation}},
            '__virtualname__': 'nonsense',
            '__file__': '/lost/in/funny/translation.py'
        }
        assert salt.utils.get_module_environment(_globals) == expectation
