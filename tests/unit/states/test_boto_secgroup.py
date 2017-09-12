# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.case import TestCase

# Import Salt Libs
import salt.states.boto_secgroup as boto_secgroup
from salt.utils.odict import OrderedDict


class Boto_SecgroupTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.states.boto_secgroup module
    '''
    def setup_loader_modules(self):
        return {boto_secgroup: {}}

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
