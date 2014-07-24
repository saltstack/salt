# -*- coding: utf-8 -*-

# import Python Libs
from collections import OrderedDict

# Import Salt Libs
from salt.modules import boto_secgroup

# Import Salt Testing Libs
from salttesting import TestCase


class Boto_SecgroupTestCase(TestCase):
    '''
    TestCase for salt.modules.boto_secgroup module
    '''
    def test__split_rules(self):
        '''
        tests the splitting of a list of rules into individual rules
        '''
        rules = [OrderedDict([('ip_protocol', u'tcp'), ('from_port', 22), ('to_port', 22), ('grants', [OrderedDict([('cidr_ip', u'0.0.0.0/0')])])]),
                 OrderedDict([('ip_protocol', u'tcp'), ('from_port', 80), ('to_port', 80), ('grants', [OrderedDict([('cidr_ip', u'0.0.0.0/0')])])])]
        split_rules = [{'to_port': 22, 'from_port': 22, 'ip_protocol': u'tcp', 'cidr_ip': u'0.0.0.0/0'},
                       {'to_port': 80, 'from_port': 80, 'ip_protocol': u'tcp', 'cidr_ip': u'0.0.0.0/0'}]
        self.assertEqual(boto_secgroup._split_rules(rules), split_rules)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(Boto_SecgroupTestCase)
