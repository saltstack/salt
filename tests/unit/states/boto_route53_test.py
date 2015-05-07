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
from salt.states import boto_route53

boto_route53.__salt__ = {}
boto_route53.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoRoute53TestCase(TestCase):
    '''
    Test cases for salt.states.boto_route53
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the Route53 record is present.
        '''
        name = 'test.example.com.'
        value = '1.1.1.1'
        zone = 'example.com.'
        record_type = 'A'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[{}, {}, {'value': ''}, False])
        mock_bool = MagicMock(return_value=False)
        with patch.dict(boto_route53.__salt__,
                        {'boto_route53.get_record': mock,
                         'boto_route53.add_record': mock_bool}):
            with patch.dict(boto_route53.__opts__, {'test': False}):
                comt = ('Failed to add {0} Route53 record.'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(boto_route53.present(name, value, zone,
                                                          record_type), ret)

            with patch.dict(boto_route53.__opts__, {'test': True}):
                comt = ('Route53 record {0} set to be added.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_route53.present(name, value, zone,
                                                          record_type), ret)

                comt = ('Route53 record {0} set to be updated.'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(boto_route53.present(name, value, zone,
                                                          record_type), ret)

            ret.update({'comment': '', 'result': True})
            self.assertDictEqual(boto_route53.present(name, value, zone,
                                                      record_type), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the Route53 record is deleted.
        '''
        name = 'test.example.com.'
        zone = 'example.com.'
        record_type = 'A'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(boto_route53.__salt__,
                        {'boto_route53.get_record': mock}):
            comt = ('{0} does not exist.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_route53.absent(name, zone, record_type),
                                 ret)

            with patch.dict(boto_route53.__opts__, {'test': True}):
                comt = ('Route53 record {0} set to be deleted.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_route53.absent(name, zone,
                                                         record_type), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BotoRoute53TestCase, needs_daemon=False)
