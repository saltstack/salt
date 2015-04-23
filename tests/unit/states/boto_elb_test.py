# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import copy

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
from salt.states import boto_elb

boto_elb.__salt__ = {}
boto_elb.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoElbTestCase(TestCase):
    '''
    Test cases for salt.states.boto_elb
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the IAM role exists.
        '''
        name = 'myelb'
        listeners = [{'elb_port': 'ELBPORT', 'instance_port': 'PORT',
                      'elb_protocol': 'HTTPS', 'certificate': 'A'}]
        attributes = {'alarm_actions': ['arn:aws:sns:us-east-1:12345:myalarm'],
                      'insufficient_data_actions': [],
                      'ok_actions': ['arn:aws:sns:us-east-1:12345:myalarm']}
        avail_zones = ['us-east-1a', 'us-east-1c', 'us-east-1d']
        alarms = {'alarm_actions': {'name': name,
                                    'attributes': {'description': 'A'}}}

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}
        ret1 = copy.deepcopy(ret)

        mock = MagicMock(return_value={})
        mock_bool = MagicMock(return_value=False)
        with patch.dict(boto_elb.__salt__,
                        {'config.option': mock,
                         'boto_elb.exists': mock_bool,
                         'boto_elb.create': mock_bool,
                         'boto_elb.get_attributes': mock}):
            with patch.dict(boto_elb.__opts__, {'test': False}):
                comt = (' Failed to create myelb ELB.')
                ret.update({'comment': comt})
                self.assertDictEqual(boto_elb.present
                                     (name, listeners, attributes=attributes,
                                      availability_zones=avail_zones), ret)

        mock = MagicMock(return_value={})
        mock_ret = MagicMock(return_value={'result': {'result': False}})
        comt1 = ('   Failed to retrieve health_check for ELB myelb.')
        with patch.dict(boto_elb.__salt__,
                        {'config.option': mock,
                         'boto_elb.get_attributes': mock,
                         'boto_elb.get_health_check': mock,
                         'boto_elb.get_elb_config': mock,
                         'state.single': mock_ret}):
            with patch.dict(boto_elb.__opts__, {'test': False}):
                ret1.update({'result': True})
                mock_elb_present = MagicMock(return_value=ret1)
                with patch.object(boto_elb, '_elb_present', mock_elb_present):
                    comt = ('  Failed to retrieve attributes for ELB myelb.')
                    ret.update({'comment': comt})
                    self.assertDictEqual(boto_elb.present
                                         (name, listeners), ret)

                    with patch.object(boto_elb, '_attributes_present',
                                      mock_elb_present):
                        ret.update({'comment': comt1})
                        self.assertDictEqual(boto_elb.present
                                             (name, listeners), ret)

                        with patch.object(boto_elb, '_health_check_present',
                                          mock_elb_present):
                            comt = ('    Failed to retrieve ELB myelb.')
                            ret.update({'comment': comt})
                            self.assertDictEqual(boto_elb.present
                                                 (name, listeners), ret)

                            with patch.object(boto_elb, '_cnames_present',
                                              mock_elb_present):
                                comt = ('     ')
                                ret.update({'comment': comt})
                                self.assertDictEqual(boto_elb.present
                                                     (name, listeners,
                                                      alarms=alarms), ret)

                                with patch.object(boto_elb, '_alarms_present',
                                                  mock_elb_present):
                                    ret.update({'result': True})
                                    self.assertDictEqual(boto_elb.present
                                                         (name, listeners,
                                                          alarms=alarms), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the IAM role is deleted.
        '''
        name = 'new_table'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(boto_elb.__salt__, {'boto_elb.exists': mock}):
            comt = ('{0} ELB does not exist.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_elb.absent(name), ret)

            with patch.dict(boto_elb.__opts__, {'test': True}):
                comt = ('ELB {0} is set to be removed.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_elb.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoElbTestCase, needs_daemon=False)
