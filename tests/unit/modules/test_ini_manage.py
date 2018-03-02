# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import tempfile

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils
import salt.modules.ini_manage as ini


class IniManageTestCase(TestCase):

    TEST_FILE_CONTENT = os.linesep.join([
        '# Comment on the first line',
        '',
        '# First main option',
        'option1=main1',
        '',
        '# Second main option',
        'option2=main2',
        '',
        '',
        '[main]',
        '# Another comment',
        'test1=value 1',
        '',
        'test2=value 2',
        '',
        '[SectionB]',
        'test1=value 1B',
        '',
        '# Blank line should be above',
        'test3 = value 3B',
        '',
        '[SectionC]',
        '# The following option is empty',
        'empty_option='
    ])

    maxDiff = None

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile(delete=False, mode='w+b')
        self.tfile.write(salt.utils.stringutils.to_bytes(self.TEST_FILE_CONTENT))
        self.tfile.close()

    def tearDown(self):
        os.remove(self.tfile.name)

    def test_get_option(self):
        self.assertEqual(
            ini.get_option(self.tfile.name, 'main', 'test1'),
            'value 1')
        self.assertEqual(
            ini.get_option(self.tfile.name, 'main', 'test2'),
            'value 2')
        self.assertEqual(
            ini.get_option(self.tfile.name, 'SectionB', 'test1'),
            'value 1B')
        self.assertEqual(
            ini.get_option(self.tfile.name, 'SectionB', 'test3'),
            'value 3B')
        self.assertEqual(
            ini.get_option(self.tfile.name, 'SectionC', 'empty_option'),
            '')

    def test_get_section(self):
        self.assertEqual(
            ini.get_section(self.tfile.name, 'SectionB'),
            {'test1': 'value 1B', 'test3': 'value 3B'})

    def test_remove_option(self):
        self.assertEqual(
            ini.remove_option(self.tfile.name, 'SectionB', 'test1'),
            'value 1B')
        self.assertIsNone(ini.get_option(self.tfile.name, 'SectionB', 'test1'))

    def test_remove_section(self):
        self.assertEqual(
            ini.remove_section(self.tfile.name, 'SectionB'),
            {'test1': 'value 1B', 'test3': 'value 3B'})
        self.assertEqual(ini.get_section(self.tfile.name, 'SectionB'), {})

    def test_set_option(self):
        result = ini.set_option(self.tfile.name, {
            'SectionB': {
                'test3': 'new value 3B',
                'test_set_option': 'test_set_value'
            },
            'SectionD': {
                'test_set_option2': 'test_set_value1'
            }
        })
        self.assertEqual(result, {
            'SectionB': {'test3': {'after': 'new value 3B',
                                   'before': 'value 3B'},
                         'test_set_option': {'after': 'test_set_value',
                                             'before': None}
            },
            'SectionD': {'after': {'test_set_option2': 'test_set_value1'},
                         'before': None
            }
        })
        # Check existing option updated
        self.assertEqual(
            ini.get_option(self.tfile.name, 'SectionB', 'test3'),
            'new value 3B')
        # Check new section and option added
        self.assertEqual(
            ini.get_option(self.tfile.name, 'SectionD', 'test_set_option2'),
            'test_set_value1')

    def test_empty_value_preserved_after_edit(self):
        ini.set_option(self.tfile.name, {
            'SectionB': {'test3': 'new value 3B'},
        })
        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            file_content = salt.utils.stringutils.to_unicode(fp.read())
        expected = '{0}{1}{0}'.format(os.linesep, 'empty_option = ')
        self.assertIn(expected, file_content, 'empty_option was not preserved')

    def test_empty_lines_preserved_after_edit(self):
        ini.set_option(self.tfile.name, {
            'SectionB': {'test3': 'new value 3B'},
        })
        expected = os.linesep.join([
            '# Comment on the first line',
            '',
            '# First main option',
            'option1 = main1',
            '',
            '# Second main option',
            'option2 = main2',
            '',
            '[main]',
            '# Another comment',
            'test1 = value 1',
            '',
            'test2 = value 2',
            '',
            '[SectionB]',
            'test1 = value 1B',
            '',
            '# Blank line should be above',
            'test3 = new value 3B',
            '',
            '[SectionC]',
            '# The following option is empty',
            'empty_option = ',
            ''
        ])
        with salt.utils.files.fopen(self.tfile.name, 'r') as fp:
            file_content = salt.utils.stringutils.to_unicode(fp.read())
        self.assertEqual(expected, file_content)

    def test_empty_lines_preserved_after_multiple_edits(self):
        ini.set_option(self.tfile.name, {
            'SectionB': {'test3': 'this value will be edited two times'},
        })
        self.test_empty_lines_preserved_after_edit()
