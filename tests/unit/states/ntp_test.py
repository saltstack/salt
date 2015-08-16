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
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import ntp

ntp.__salt__ = {}
ntp.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NtpTestCase(TestCase):
    '''
    Test cases for salt.states.ntp
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NtpTestCase, needs_daemon=False)
