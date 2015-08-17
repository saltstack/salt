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
from salt.states import boto_asg

boto_asg.__salt__ = {}
boto_asg.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoAsgTestCase(TestCase):
    '''
    Test cases for salt.states.boto_asg
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the autoscale group exists.
        '''
        name = 'myasg'
        launch_config_name = 'mylc'
        availability_zones = ['us-east-1a', 'us-east-1b']
        min_size = 1
        max_size = 1

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, {'min_size': 2}, ['']])
        with patch.dict(boto_asg.__salt__, {'boto_asg.get_config': mock}):
            with patch.dict(boto_asg.__opts__, {'test': True}):
                comt = ('Autoscale group set to be created.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_asg.present(name, launch_config_name,
                                                      availability_zones,
                                                      min_size, max_size), ret)

                comt = ('Autoscale group set to be updated.')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_asg.present(name, launch_config_name,
                                                      availability_zones,
                                                      min_size, max_size), ret)

                with patch.dict(boto_asg.__salt__,
                                {'config.option': MagicMock(return_value={})}):
                    comt = ('Autoscale group present. ')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(boto_asg.present(name,
                                                          launch_config_name,
                                                          availability_zones,
                                                          min_size, max_size),
                                         ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named autoscale group is deleted.
        '''
        name = 'myasg'

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(boto_asg.__salt__, {'boto_asg.get_config': mock}):
            with patch.dict(boto_asg.__opts__, {'test': True}):
                comt = ('Autoscale group set to be deleted.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_asg.absent(name), ret)

                comt = ('Autoscale group does not exist.')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(boto_asg.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoAsgTestCase, needs_daemon=False)
