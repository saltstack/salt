# -*- coding: utf-8 -*-
'''
unittests for yaml outputter
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase

# Import Salt Libs
from salt.output import yaml_out as yaml


class YamlTestCase(TestCase):
    '''
    Test cases for salt.output.json_out
    '''
    def setUp(self):
        # reset to default behavior
        yaml.__opts__ = {}
        self.data = {'test': 'two', 'example': 'one'}

    def test_default_output(self):
        ret = yaml.output(self.data)
        expect = 'example: one\ntest: two\n'
        self.assertEqual(expect, ret)

    def test_negative_int_output(self):
        yaml.__opts__['output_indent'] = -1
        ret = yaml.output(self.data)
        expect = '{example: one, test: two}\n'
        self.assertEqual(expect, ret)
