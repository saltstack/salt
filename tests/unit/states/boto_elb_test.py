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
        alarms = {'MyAlarm': {'name': name,
                              'attributes': {'description': 'A'}}}
        attrs = {'alarm_actions': ['arn:aws:sns:us-east-1:12345:myalarm'],
                 'insufficient_data_actions': [],
                 'ok_actions': ['arn:aws:sns:us-east-1:12345:myalarm']}
        health_check = {'target:': 'HTTP:80/'}
        avail_zones = ['us-east-1a', 'us-east-1c', 'us-east-1d']
        cnames = [{'name': 'www.test.com', 'zone': 'test.com', 'ttl': 60}]

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}
        ret1 = copy.deepcopy(ret)

        mock = MagicMock(return_value={})
        mock_false_bool = MagicMock(return_value=False)
        mock_true_bool = MagicMock(return_value=True)
        mock_attributes = MagicMock(return_value=attrs)
        mock_health_check = MagicMock(return_value=health_check)
        mock_ret = MagicMock(return_value={'myelb': ret1})

        mock = MagicMock(return_value={})
        with patch.dict(boto_elb.__salt__,
                        {'config.option': mock,
                         'boto_elb.exists': mock_false_bool,
                         'boto_elb.create': mock_false_bool}):
            with patch.dict(boto_elb.__opts__, {'test': False}):
                ret = boto_elb.present(
                    name,
                    listeners,
                    availability_zones=avail_zones
                )
                self.assertTrue(boto_elb.__salt__['boto_elb.exists'].called)
                self.assertTrue(boto_elb.__salt__['boto_elb.create'].called)
                self.assertIn('Failed to create myelb ELB.', ret['comment'])
                self.assertFalse(ret['result'])

        mock = MagicMock(return_value={})
        mock_ret = MagicMock(return_value={'myelb': ret1})
        with patch.dict(boto_elb.__salt__,
                        {'config.option': mock,
                         'boto_elb.exists': mock_false_bool,
                         'boto_elb.create': mock_true_bool,
                         'boto_elb.get_attributes': mock_attributes,
                         'boto_elb.get_health_check': mock_health_check,
                         'boto_elb.get_elb_config': mock,
                         'state.single': mock_ret}):
            with patch.dict(boto_elb.__opts__, {'test': False}):
                ret = boto_elb.present(
                    name,
                    listeners,
                    availability_zones=avail_zones,
                    health_check=health_check,
                    alarms=alarms
                )
                self.assertTrue(boto_elb.__salt__['boto_elb.exists'].called)
                self.assertTrue(boto_elb.__salt__['boto_elb.create'].called)
                self.assertTrue(boto_elb.__salt__['state.single'].called)
                self.assertFalse(
                    boto_elb.__salt__['boto_elb.get_attributes'].called
                )
                self.assertTrue(
                    boto_elb.__salt__['boto_elb.get_health_check'].called
                )
                self.assertIn('ELB myelb created.', ret['comment'])
                self.assertTrue(ret['result'])

        mock = MagicMock(return_value={})
        mock_elb = MagicMock(return_value={'dns_name': 'myelb.amazon.com'})
        mock_ret = MagicMock(return_value={'myelb': ret1})
        with patch.dict(boto_elb.__salt__,
                        {'config.option': mock,
                         'boto_elb.exists': mock_false_bool,
                         'boto_elb.create': mock_true_bool,
                         'boto_elb.get_attributes': mock_attributes,
                         'boto_elb.get_health_check': mock_health_check,
                         'boto_elb.get_elb_config': mock_elb,
                         'state.single': mock_ret}):
            with patch.dict(boto_elb.__opts__, {'test': False}):
                ret = boto_elb.present(
                    name,
                    listeners,
                    availability_zones=avail_zones,
                    health_check=health_check,
                    cnames=cnames
                )
                self.assertTrue(boto_elb.__salt__['state.single'].called)
                cname_call = boto_elb.__salt__['state.single'].mock_calls[0]
                self.assertEqual(
                    cname_call[1][0],
                    'boto_route53.present'
                )
                self.assertTrue(ret['result'])

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
