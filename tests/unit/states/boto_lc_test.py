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
from salt.exceptions import SaltInvocationError

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import boto_lc

boto_lc.__salt__ = {}
boto_lc.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoLcTestCase(TestCase):
    '''
    Test cases for salt.states.boto_lc
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the launch configuration exists.
        '''
        name = 'mylc'
        image_id = 'ami-0b9c9f62'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        self.assertRaises(SaltInvocationError, boto_lc.present, name,
                          image_id, user_data=True, cloud_init=True)

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(boto_lc.__salt__,
                        {'boto_asg.launch_configuration_exists': mock}):
            comt = ('Launch configuration present.')
            ret.update({'comment': comt})
            self.assertDictEqual(boto_lc.present(name, image_id), ret)

            with patch.dict(boto_lc.__opts__, {'test': True}):
                comt = ('Launch configuration set to be created.')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_lc.present(name, image_id), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named launch configuration is deleted.
        '''
        name = 'mylc'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(boto_lc.__salt__,
                        {'boto_asg.launch_configuration_exists': mock}):
            comt = ('Launch configuration does not exist.')
            ret.update({'comment': comt})
            self.assertDictEqual(boto_lc.absent(name), ret)

            with patch.dict(boto_lc.__opts__, {'test': True}):
                comt = ('Launch configuration set to be deleted.')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_lc.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoLcTestCase, needs_daemon=False)
