# -*- coding: utf-8 -*-
'''
unittests for json outputter
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import patch

# Import Salt Libs
import salt.output.json_out as json_out
import salt.utils.stringutils
from salt.ext import six


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
            decoded = {'test': 'Д', 'example': 'one'}
            encoded = {'test': salt.utils.stringutils.to_str('Д'), 'example': 'one'}
            # json.dumps on Python 2 adds a space before a newline while in the
            # process of dumping a dictionary.
            if six.PY2:
                expected = salt.utils.stringutils.to_str('{\n    "example": "one", \n    "test": "Д"\n}')
            else:
                expected = '{\n    "example": "one",\n    "test": "Д"\n}'
            self.assertEqual(json_out.output(decoded), expected)
            self.assertEqual(json_out.output(encoded), expected)
