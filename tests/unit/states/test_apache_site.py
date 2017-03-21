# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.apache_site as apache_site

apache_site.__opts__ = {}
apache_site.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ApacheSiteTestCase(TestCase):
    '''
    Test cases for salt.states.apache_site
    '''
    # 'enabled' function tests: 1

    def test_enabled(self):
        '''
        Test to ensure an Apache site is enabled.
        '''
        name = 'saltstack.com'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, False])
        mock_str = MagicMock(return_value={'Status': ['enabled']})
        with patch.dict(apache_site.__salt__,
                        {'apache.check_site_enabled': mock,
                         'apache.a2ensite': mock_str}):
            comt = ('{0} already enabled.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(apache_site.enabled(name), ret)

            comt = ('Apache site {0} is set to be enabled.'.format(name))
            ret.update({'comment': comt, 'result': None,
                        'changes': {'new': name, 'old': None}})
            with patch.dict(apache_site.__opts__, {'test': True}):
                self.assertDictEqual(apache_site.enabled(name), ret)

            comt = ('Failed to enable {0} Apache site'.format(name))
            ret.update({'comment': comt, 'result': False, 'changes': {}})
            with patch.dict(apache_site.__opts__, {'test': False}):
                self.assertDictEqual(apache_site.enabled(name), ret)

    # 'disabled' function tests: 1

    def test_disabled(self):
        '''
        Test to ensure an Apache site is disabled.
        '''
        name = 'saltstack.com'

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, True, False])
        mock_str = MagicMock(return_value={'Status': ['disabled']})
        with patch.dict(apache_site.__salt__,
                        {'apache.check_site_enabled': mock,
                         'apache.a2dissite': mock_str}):
            comt = ('Apache site {0} is set to be disabled.'.format(name))
            ret.update({'comment': comt, 'changes': {'new': None, 'old': name}})
            with patch.dict(apache_site.__opts__, {'test': True}):
                self.assertDictEqual(apache_site.disabled(name), ret)

            comt = ('Failed to disable {0} Apache site'.format(name))
            ret.update({'comment': comt, 'result': False,
                        'changes': {}})
            with patch.dict(apache_site.__opts__, {'test': False}):
                self.assertDictEqual(apache_site.disabled(name), ret)

            comt = ('{0} already disabled.'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(apache_site.disabled(name), ret)
