# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.filebuffer_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
from salt.utils.filebuffer import BufferedReader, InvalidFileMode


class TestFileBuffer(TestCase):
    def test_read_only_mode(self):
        with self.assertRaises(InvalidFileMode):
            BufferedReader('/tmp/foo', mode='a')

        with self.assertRaises(InvalidFileMode):
            BufferedReader('/tmp/foo', mode='ab')

        with self.assertRaises(InvalidFileMode):
            BufferedReader('/tmp/foo', mode='w')

        with self.assertRaises(InvalidFileMode):
            BufferedReader('/tmp/foo', mode='wb')
