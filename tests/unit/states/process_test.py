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
from salt.states import process

process.__opts__ = {}
process.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ProcessTestCase(TestCase):
    '''
    Test cases for salt.states.process
    '''
    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensures that the named command is not running.
        '''
        name = 'apache2'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        mock = MagicMock(return_value='')
        with patch.dict(process.__salt__, {'ps.pgrep': mock,
                                           'ps.pkill': mock}):
            with patch.dict(process.__opts__, {'test': True}):
                comt = ('No matching processes running')
                ret.update({'comment': comt})
                self.assertDictEqual(process.absent(name), ret)

            with patch.dict(process.__opts__, {'test': False}):
                ret.update({'result': True})
                self.assertDictEqual(process.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ProcessTestCase, needs_daemon=False)
