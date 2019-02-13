# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.utils.filebuffer_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.helpers import generate_random_name

# Import salt libs
import salt.modules.cmdmod as cmdmod
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

    def test_issue_51309(self):
        '''
        https://github.com/saltstack/salt/issues/51309
        '''
        temp_name = os.path.join(os.environ.get('TEMP'),
                                 generate_random_name(prefix='salt-test-'))
        cmd = 'tzutil /l > {0}'.format(temp_name)
        cmdmod.run(cmd=cmd, python_shell=True)

        def find_value(text):
            stripped_text = text.strip()
            try:
                with BufferedReader(temp_name) as breader:
                    for chunk in breader:
                        if stripped_text in chunk:
                            return True
                return False
            except (IOError, OSError):
                return False

        self.assertTrue(find_value('(UTC) Coordinated Universal Time'))
        os.remove(temp_name)
