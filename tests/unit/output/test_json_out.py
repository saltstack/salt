# -*- coding: utf-8 -*-
'''
unittests for json outputter
'''

# Import Python Libs
from __future__ import absolute_import
import json

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import patch

# Import Salt Libs
import salt.output.json_out as json_out

# Import 3rd-party libs
import salt.ext.six as six


class JsonTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.output.json_out
    '''
    def setup_loader_modules(self):
        return {json_out: {}}

    def setUp(self):
        self.data = {'test': 'two', 'example': 'one'}
        self.addCleanup(delattr, self, 'data')

    def test_default_output(self):
        ret = json_out.output(self.data)
        self.assertIn('"test": "two"', ret)
        self.assertIn('"example": "one"', ret)

    def test_pretty_output(self):
        with patch.dict(json_out.__opts__, {'output_indent': 'pretty'}):
            ret = json_out.output(self.data)
            self.assertIn('"test": "two"', ret)
            self.assertIn('"example": "one"', ret)

    def test_indent_output(self):
        with patch.dict(json_out.__opts__, {'output_indent': 2}):
            ret = json_out.output(self.data)
            self.assertIn('"test": "two"', ret)
            self.assertIn('"example": "one"', ret)

    def test_negative_zero_output(self):
        with patch.dict(json_out.__opts__, {'output_indent': 0}):
            ret = json_out.output(self.data)
            self.assertIn('"test": "two"', ret)
            self.assertIn('"example": "one"', ret)

    def test_negative_int_output(self):
        with patch.dict(json_out.__opts__, {'output_indent': -1}):
            ret = json_out.output(self.data)
            self.assertIn('"test": "two"', ret)
            self.assertIn('"example": "one"', ret)

    def test_unicode_output(self):
        with patch.dict(json_out.__opts__, {'output_indent': 'pretty'}):
            data = {'test': '\xe1', 'example': 'one'}
            expect = ('{"message": "\'utf8\' codec can\'t decode byte 0xe1 in position 0: unexpected end of data", '
                      '"error": "Unable to serialize output to json"}')
            ret = json_out.output(data)
            if six.PY2:
                self.assertEqual(expect, ret)
            else:
                self.assertEqual(json.loads(ret), data)
