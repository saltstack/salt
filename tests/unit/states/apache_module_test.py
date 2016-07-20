# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import apache_module

apache_module.__opts__ = {}
apache_module.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ApacheModuleTestCase(TestCase):
    '''
    Test cases for salt.states.apache_module
    '''
    # 'enable' function tests: 1

    def test_enable(self):
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
            comt = ('{0} already enabled.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(apache_module.enable(name), ret)

            comt = ('Apache module {0} is set to be enabled.'.format(name))
            ret.update({'comment': comt, 'result': None,
                        'changes': {'new': 'cgi', 'old': None}})
            with patch.dict(apache_module.__opts__, {'test': True}):
                self.assertDictEqual(apache_module.enable(name), ret)

            comt = ('Failed to enable {0} Apache module'.format(name))
            ret.update({'comment': comt, 'result': False, 'changes': {}})
            with patch.dict(apache_module.__opts__, {'test': False}):
                self.assertDictEqual(apache_module.enable(name), ret)

    # 'disable' function tests: 1

    def test_disable(self):
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
            comt = ('Apache module {0} is set to be disabled.'.format(name))
            ret.update({'comment': comt, 'changes': {'new': None, 'old': 'cgi'}})
            with patch.dict(apache_module.__opts__, {'test': True}):
                self.assertDictEqual(apache_module.disable(name), ret)

            comt = ('Failed to disable {0} Apache module'.format(name))
            ret.update({'comment': comt, 'result': False,
                        'changes': {}})
            with patch.dict(apache_module.__opts__, {'test': False}):
                self.assertDictEqual(apache_module.disable(name), ret)

            comt = ('{0} already disabled.'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(apache_module.disable(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ApacheModuleTestCase, needs_daemon=False)
