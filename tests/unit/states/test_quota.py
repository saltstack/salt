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
    patch
)

# Import Salt Libs
from salt.states import quota

quota.__opts__ = {}
quota.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class QuotaTestCase(TestCase):
    '''
    Test cases for salt.states.quota
    '''
    # 'mode' function tests: 1

    def test_mode(self):
        '''
        Test to set the quota for the system.
        '''
        name = '/'
        mode = True
        quotatype = 'user'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_bool = MagicMock(side_effect=[True, False])
        mock = MagicMock(return_value={name: {quotatype: 'on'}})
        with patch.dict(quota.__salt__, {'quota.get_mode': mock}):
            comt = ('Quota for / already set to on')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(quota.mode(name, mode, quotatype), ret)

        mock = MagicMock(return_value={name: {quotatype: 'off'}})
        with patch.dict(quota.__salt__, {'quota.get_mode': mock,
                                         'quota.on': mock_bool}):
            with patch.dict(quota.__opts__, {'test': True}):
                comt = ('Quota for / needs to be set to on')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(quota.mode(name, mode, quotatype), ret)

            with patch.dict(quota.__opts__, {'test': False}):
                comt = ('Set quota for / to on')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'quota': name}})
                self.assertDictEqual(quota.mode(name, mode, quotatype), ret)

                comt = ('Failed to set quota for / to on')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(quota.mode(name, mode, quotatype), ret)
