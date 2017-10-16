# -*- coding: utf-8 -*-
'''
unittests for json outputter
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.output import json_out as json


class JsonTestCase(TestCase):
    '''
    Test cases for salt.output.json_out
    '''
    def setUp(self):
        json.__opts__ = {}
        self.data = {'test': 'two', 'example': 'one'}

    def test_default_output(self):
        ret = json.output(self.data)
        expect = '{\n    "test": "two", \n    "example": "one"\n}'
        self.assertEqual(expect, ret)

    def test_pretty_output(self):
        json.__opts__['output_indent'] = 'pretty'
        ret = json.output(self.data)
        expect = '{\n    "example": "one", \n    "test": "two"\n}'
        self.assertEqual(expect, ret)

    def test_indent_output(self):
        json.__opts__['output_indent'] = 2
        expect = '{\n  "test": "two", \n  "example": "one"\n}'
        ret = json.output(self.data)
        self.assertEqual(expect, ret)

    def test_negative_zero_output(self):
        json.__opts__['output_indent'] = 0
        expect = '{\n"test": "two", \n"example": "one"\n}'
        ret = json.output(self.data)
        self.assertEqual(expect, ret)

    def test_negative_int_output(self):
        json.__opts__['output_indent'] = -1
        expect = '{"test": "two", "example": "one"}'
        ret = json.output(self.data)
        self.assertEqual(expect, ret)

    def test_unicode_output(self):
        json.__opts__['output_indent'] = 'pretty'
        data = {'test': '\xe1', 'example': 'one'}
        expect = ('{"message": "\'utf8\' codec can\'t decode byte 0xe1 in position 0: unexpected end of data", '
                  '"error": "Unable to serialize output to json"}')
        ret = json.output(data)
        self.assertEqual(expect, ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(JsonTestCase, needs_daemon=False)
