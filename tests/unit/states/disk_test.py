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
from salt.states import disk

disk.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DiskTestCase(TestCase):
    '''
    Test cases for salt.states.disk
    '''
    # 'status' function tests: 1

    def test_status(self):
        '''
        Test to return the current disk usage stats for the named mount point
        '''
        name = 'mydisk'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {},
               'data': {}}

        mock = MagicMock(side_effect=[[], [name], {name: {'capacity': '8 %'}},
                                      {name: {'capacity': '22 %'}},
                                      {name: {'capacity': '15 %'}}])
        with patch.dict(disk.__salt__, {'disk.usage': mock}):
            comt = ('Named disk mount not present ')
            ret.update({'comment': comt})
            self.assertDictEqual(disk.status(name), ret)

            comt = ('Min must be less than max')
            ret.update({'comment': comt})
            self.assertDictEqual(disk.status(name, '10 %', '20 %'), ret)

            comt = ('Disk is below minimum of 10 at 8')
            ret.update({'comment': comt, 'data': {'capacity': '8 %'}})
            self.assertDictEqual(disk.status(name, '20 %', '10 %'), ret)

            comt = ('Disk is above maximum of 20 at 22')
            ret.update({'comment': comt, 'data': {'capacity': '22 %'}})
            self.assertDictEqual(disk.status(name, '20 %', '10 %'), ret)

            comt = ('Disk in acceptable range')
            ret.update({'comment': comt, 'result': True,
                        'data': {'capacity': '15 %'}})
            self.assertDictEqual(disk.status(name, '20 %', '10 %'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DiskTestCase, needs_daemon=False)
