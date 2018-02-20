# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.ntp as ntp


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NtpTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.ntp
    '''
    def setup_loader_modules(self):
        return {ntp: {}}

    # 'managed' function tests: 1

    def test_managed(self):
        '''
        Test to manage NTP servers.
        '''
        name = 'coffee-script'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_lst = MagicMock(return_value=[])
        with patch.dict(ntp.__salt__, {'ntp.get_servers': mock_lst,
                                       'ntp.set_servers': mock_lst}):
            comt = ('NTP servers already configured as specified')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ntp.managed(name, []), ret)

            with patch.dict(ntp.__opts__, {'test': True}):
                comt = ('NTP servers will be updated to: coffee-script')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(ntp.managed(name, [name]), ret)

            with patch.dict(ntp.__opts__, {'test': False}):
                comt = ('Failed to update NTP servers')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(ntp.managed(name, [name]), ret)
