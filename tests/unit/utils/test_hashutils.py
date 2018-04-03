# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.utils.hashutils


class HashutilsTestCase(TestCase):

    def test_get_hash_exception(self):
        self.assertRaises(
            ValueError,
            salt.utils.hashutils.get_hash,
            '/tmp/foo/',
            form='INVALID')
