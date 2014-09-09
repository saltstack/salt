# -*- coding: utf-8 -*-

# import Python Libs
from collections import OrderedDict

# Import Salt Libs
from salt.states import boto_secgroup

# Import Salt Testing Libs
from salttesting import TestCase


class Boto_SecgroupTestCase(TestCase):
    '''
    TestCase for salt.states.boto_secgroup module
    '''
    def test__get_rule_changes_no_rules_no_change(self):
        '''
        tests a condition with no rules in present or desired group
        '''
        present_rules = []
        desired_rules = []
        self.assertEqual(boto_secgroup._get_rule_changes(desired_rules, present_rules), ([], []))

    def test__get_rule_changes_create_rules(self):
        '''
        tests a condition where a rule must be created
        '''
        present_rules = [OrderedDict([('ip_protocol', 'tcp'), ('from_port', 22), ('to_port', 22), ('cidr_ip', '0.0.0.0/0')])]
        desired_rules = [OrderedDict([('ip_protocol', 'tcp'), ('from_port', 22), ('to_port', 22), ('cidr_ip', '0.0.0.0/0')]),
                         OrderedDict([('ip_protocol', 'tcp'), ('from_port', 80), ('to_port', 80), ('cidr_ip', '0.0.0.0/0')])]
        # can also use: rules_to_create = [rule for rule in desired_rules if rule not in present_rules]
        rules_to_create = [OrderedDict([('ip_protocol', 'tcp'), ('from_port', 80), ('to_port', 80), ('cidr_ip', '0.0.0.0/0')])]
        self.assertEqual(boto_secgroup._get_rule_changes(desired_rules, present_rules), ([], rules_to_create))

    def test__get_rule_changes_delete_rules(self):
        '''
        tests a condition where a rule must be deleted
        '''
        present_rules = [OrderedDict([('ip_protocol', 'tcp'), ('from_port', 22), ('to_port', 22), ('cidr_ip', '0.0.0.0/0')]),
                         OrderedDict([('ip_protocol', 'tcp'), ('from_port', 80), ('to_port', 80), ('cidr_ip', '0.0.0.0/0')])]
        desired_rules = [OrderedDict([('ip_protocol', 'tcp'), ('from_port', 22), ('to_port', 22), ('cidr_ip', '0.0.0.0/0')])]
        # can also use: rules_to_delete = [rule for rule in present_rules if rule not in desired_rules]
        rules_to_delete = [OrderedDict([('ip_protocol', 'tcp'), ('from_port', 80), ('to_port', 80), ('cidr_ip', '0.0.0.0/0')])]
        self.assertEqual(boto_secgroup._get_rule_changes(desired_rules, present_rules), (rules_to_delete, []))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(Boto_SecgroupTestCase)
