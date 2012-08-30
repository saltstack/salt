# -*- coding: utf-8 -*-
'''
    tests.unit.utils.filebuffer_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
'''


from saltunittest import TestCase, TestLoader, TextTestRunner

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

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestFileBuffer)
    TextTestRunner(verbosity=1).run(tests)
