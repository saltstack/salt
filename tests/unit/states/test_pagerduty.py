# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.pagerduty as pagerduty

pagerduty.__salt__ = {}
pagerduty.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PagerdutyTestCase(TestCase):
    '''
    Test cases for salt.states.pagerduty
    '''
    # 'create_event' function tests: 1

    def test_create_event(self):
        '''
        Test to create an event on the PagerDuty service.
        '''
        name = 'This is a server warning message'
        details = 'This is a much more detailed message'
        service_key = '9abcd123456789efabcde362783cdbaf'
        profile = 'my-pagerduty-account'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        with patch.dict(pagerduty.__opts__, {'test': True}):
            comt = ('Need to create event: {0}'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(pagerduty.create_event(name, details,
                                                        service_key, profile),
                                 ret)

        with patch.dict(pagerduty.__opts__, {'test': False}):
            mock_t = MagicMock(return_value=True)
            with patch.dict(pagerduty.__salt__,
                            {'pagerduty.create_event': mock_t}):
                comt = ('Created event: {0}'.format(name))
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(pagerduty.create_event(name, details,
                                                            service_key,
                                                            profile), ret)
