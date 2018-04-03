# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.apache_module as apache_module


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ApacheModuleTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.apache_module
    '''
    def setup_loader_modules(self):
        return {apache_module: {}}

    # 'enabled' function tests: 1

    def test_enabled(self):
        '''
        Test to ensure an Apache module is enabled.
        '''
        name = 'cgi'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, False])
        mock_str = MagicMock(return_value={'Status': ['enabled']})
        with patch.dict(apache_module.__salt__,
                        {'apache.check_mod_enabled': mock,
                         'apache.a2enmod': mock_str}):
            comt = '{0} already enabled.'.format(name)
            ret.update({'comment': comt})
            self.assertDictEqual(apache_module.enabled(name), ret)

            comt = 'Apache module {0} is set to be enabled.'.format(name)
            ret.update({'comment': comt, 'result': None,
                        'changes': {'new': 'cgi', 'old': None}})
            with patch.dict(apache_module.__opts__, {'test': True}):
                self.assertDictEqual(apache_module.enabled(name), ret)

            comt = 'Failed to enable {0} Apache module'.format(name)
            ret.update({'comment': comt, 'result': False, 'changes': {}})
            with patch.dict(apache_module.__opts__, {'test': False}):
                self.assertDictEqual(apache_module.enabled(name), ret)

    # 'disabled' function tests: 1

    def test_disabled(self):
        '''
        Test to ensure an Apache module is disabled.
        '''
        name = 'cgi'

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, True, False])
        mock_str = MagicMock(return_value={'Status': ['disabled']})
        with patch.dict(apache_module.__salt__,
                        {'apache.check_mod_enabled': mock,
                         'apache.a2dismod': mock_str}):
            comt = 'Apache module {0} is set to be disabled.'.format(name)
            ret.update({'comment': comt, 'changes': {'new': None, 'old': 'cgi'}})
            with patch.dict(apache_module.__opts__, {'test': True}):
                self.assertDictEqual(apache_module.disabled(name), ret)

            comt = 'Failed to disable {0} Apache module'.format(name)
            ret.update({'comment': comt, 'result': False,
                        'changes': {}})
            with patch.dict(apache_module.__opts__, {'test': False}):
                self.assertDictEqual(apache_module.disabled(name), ret)

            comt = '{0} already disabled.'.format(name)
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(apache_module.disabled(name), ret)
