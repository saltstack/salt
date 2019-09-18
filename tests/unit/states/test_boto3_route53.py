# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.boto3_route53 as boto3_route53


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoRoute53TestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto3_route53
    '''
    def setup_loader_modules(self):
        return {boto3_route53: {}}

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the Route53 record is present.
        '''
        name = 'test.example.com.'
        value = ['1.1.1.1']
        zone = 'example.com.'
        record_type = 'A'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}
        mocked_zone = []
        mocked_records = []
        change_mock = MagicMock(return_value=False)

        with patch.dict(boto3_route53.__salt__, {
            'boto3_route53.find_hosted_zone': MagicMock(return_value=mocked_zone),
            'boto3_route53.get_resource_records': MagicMock(return_value=mocked_records),
            'boto3_route53.change_resource_record_sets': change_mock}):

            with patch.dict(boto3_route53.__opts__, {'test': True}):
                comt = 'Route 53 public hosted zone example.com. not found'
                ret.update({'comment': comt})
                self.assertDictEqual(boto3_route53.rr_present(name, 
                    Name=name, DomainName=zone, Type=record_type), ret)

            with patch.dict(boto3_route53.__opts__, {'test': False}):
                comt = 'Route 53 public hosted zone example.com. not found'
                ret.update({'comment': comt})
                self.assertDictEqual(boto3_route53.rr_present(name, 
                    Name=name, DomainName=zone, Type=record_type), ret)

            mocked_zone.append({'HostedZone': {'Id': 'FAKE-ID'}}) 

            with patch.dict(boto3_route53.__opts__, {'test': True}):
                comt = 'Route 53 resource record test.example.com. with type A would be added.'
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto3_route53.rr_present(name, 
                    Name=name, DomainName=zone, Type=record_type), ret)

            with patch.dict(boto3_route53.__opts__, {'test': False}):
                comt = 'Route 53 resource record test.example.com. with type A created.'
                change_mock.return_value=True
                ret2 = ret.copy()
                ret2.update({'comment': comt})
                ret2.update({'changes': {'new': {'Name': 'test.example.com.', 'Type': 'A'}, 'old': None}})
                ret2.update({'result': True})
                self.assertDictEqual(boto3_route53.rr_present(name, 
                    Name=name, DomainName=zone, Type=record_type), ret2)

            with patch.dict(boto3_route53.__opts__, {'test': True}):
                mocked_records.append({'ResourceRecords': [{'Value': '1.1.1.1'}]})
                comt = 'Route 53 resource record test.example.com. with type A is already in the desired state.'
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(boto3_route53.rr_present(name, 
                    Name=name, ResourceRecords=value, DomainName=zone, Type=record_type), ret)

