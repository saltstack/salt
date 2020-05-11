# -*- coding: utf-8 -*-
'''
Tests for salt.utils.iam
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.iam as iam
from salt.ext import six
from tests.support.unit import TestCase, skipIf


class IamTestCase(TestCase):

    @skipIf(six.PY3, 'Only needs to run on Python 2')
    def test__convert_key_to_str(self):
        '''
        Makes sure that unicode string is converted to a str type on PY2
        '''
        key = 'foo'
        expected = key.encode('utf-8')
        self.assertEqual(iam._convert_key_to_str(key), expected)
