# -*- coding: utf-8 -*-
'''
integration tests for mac_xattr
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

test_file = os.path.join(integration.TMP, 'xattr_test_file.txt')


class MacXattrModuleTest(integration.ModuleCase):
    '''
    Validate the mac_xattr module
    '''

    def setUp(self):
        '''
        Create test file for testing extended attributes
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('xattr'):
            self.skipTest('Test requires xattr binary')

        self.run_function('file.touch', [test_file])

    def tearDown(self):
        '''
        Clean up test file
        '''
        if os.path.exists(test_file):
            os.remove(test_file)

    def test_list_none(self):
        '''
        Make sure there are no attributes
        '''
        self.run_function('xattr.clear', [test_file])
        self.assertEqual(self.run_function('xattr.list', [test_file]), {})

    def test_write(self):
        '''
        Write an attribute
        '''
        self.run_function('xattr.clear', [test_file])
        self.run_function('xattr.write', [test_file, 'spongebob', 'squarepants'])
        self.run_function('xattr.write', [test_file, 'squidward', 'plankton'])
        self.run_function('xattr.write', [test_file, 'crabby', 'patty'])
        self.assertEqual(
            self.run_function('xattr.list', [test_file]),
            {'spongebob': 'squarepants',
             'squidward': 'plankton',
             'crabby': 'patty'})

    def test_list(self):
        '''
        Test xattr.list
        '''
        self.run_function('xattr.clear', [test_file])
        self.run_function('xattr.write', [test_file, 'spongebob', 'squarepants'])
        self.run_function('xattr.write', [test_file, 'squidward', 'plankton'])
        self.run_function('xattr.write', [test_file, 'crabby', 'patty'])
        self.assertEqual(
            self.run_function('xattr.list', [test_file]),
            {'spongebob': 'squarepants',
             'squidward': 'plankton',
             'crabby': 'patty'})

    def test_read(self):
        '''
        Test xattr.read
        '''
        self.run_function('xattr.clear', [test_file])
        self.run_function('xattr.write', [test_file, 'spongebob', 'squarepants'])
        self.run_function('xattr.write', [test_file, 'squidward', 'plankton'])
        self.run_function('xattr.write', [test_file, 'crabby', 'patty'])
        self.assertEqual(
            self.run_function('xattr.read', [test_file, 'spongebob']),
            'squarepants')
        self.assertEqual(
            self.run_function('xattr.read', [test_file, 'squidward']),
            'plankton')
        self.assertEqual(
            self.run_function('xattr.read', [test_file, 'crabby']),
            'patty')

    def test_delete(self):
        '''
        Test xattr.delete
        '''
        self.run_function('xattr.clear', [test_file])
        self.run_function('xattr.write', [test_file, 'spongebob', 'squarepants'])
        self.run_function('xattr.write', [test_file, 'squidward', 'plankton'])
        self.run_function('xattr.write', [test_file, 'crabby', 'patty'])
        self.assertEqual(
            self.run_function('xattr.delete', [test_file, 'squidward']),
            '')
        self.assertEqual(
            self.run_function('xattr.list', [test_file]),
            {'spongebob': 'squarepants', 'crabby': 'patty'})

    def test_clear(self):
        '''
        Test xattr.clear
        '''
        self.run_function('xattr.clear', [test_file])
        self.run_function('xattr.write', [test_file, 'spongebob', 'squarepants'])
        self.run_function('xattr.write', [test_file, 'squidward', 'plankton'])
        self.run_function('xattr.write', [test_file, 'crabby', 'patty'])
        self.assertEqual(self.run_function('xattr.clear', [test_file]), '')
        self.assertEqual(self.run_function('xattr.list', [test_file]), {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacXattrModuleTest)
