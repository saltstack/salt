# -*- coding: utf-8 -*-
'''
integration tests for mac_xattr
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase

# Import Salt libs
import salt.utils.path
import salt.utils.platform

TEST_FILE = os.path.join(RUNTIME_VARS.TMP, 'xattr_test_file.txt')
NO_FILE = os.path.join(RUNTIME_VARS.TMP, 'xattr_no_file.txt')


class MacXattrModuleTest(ModuleCase):
    '''
    Validate the mac_xattr module
    '''

    def setUp(self):
        '''
        Create test file for testing extended attributes
        '''
        if not salt.utils.platform.is_darwin():
            self.skipTest('Test only available on macOS')

        if not salt.utils.path.which('xattr'):
            self.skipTest('Test requires xattr binary')

        self.run_function('file.touch', [TEST_FILE])

    def tearDown(self):
        '''
        Clean up test file
        '''
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)

    def test_list_no_xattr(self):
        '''
        Make sure there are no attributes
        '''
        # Clear existing attributes
        self.assertTrue(self.run_function('xattr.clear', [TEST_FILE]))

        # Test no attributes
        self.assertEqual(self.run_function('xattr.list', [TEST_FILE]), {})

        # Test file not found
        self.assertEqual(self.run_function('xattr.list', [NO_FILE]),
                         'ERROR: File not found: {0}'.format(NO_FILE))

    def test_write(self):
        '''
        Write an attribute
        '''
        # Clear existing attributes
        self.assertTrue(self.run_function('xattr.clear', [TEST_FILE]))

        # Write some attributes
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'spongebob', 'squarepants']))
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'squidward', 'plankton']))
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'crabby', 'patty']))

        # Test that they were actually added
        self.assertEqual(
            self.run_function('xattr.list', [TEST_FILE]),
            {'spongebob': 'squarepants',
             'squidward': 'plankton',
             'crabby': 'patty'})

        # Test file not found
        self.assertEqual(
            self.run_function('xattr.write', [NO_FILE, 'patrick', 'jellyfish']),
            'ERROR: File not found: {0}'.format(NO_FILE))

    def test_read(self):
        '''
        Test xattr.read
        '''
        # Clear existing attributes
        self.assertTrue(self.run_function('xattr.clear', [TEST_FILE]))

        # Write an attribute
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'spongebob', 'squarepants']))

        # Read the attribute
        self.assertEqual(
            self.run_function('xattr.read', [TEST_FILE, 'spongebob']),
            'squarepants')

        # Test file not found
        self.assertEqual(
            self.run_function('xattr.read', [NO_FILE, 'spongebob']),
            'ERROR: File not found: {0}'.format(NO_FILE))

        # Test attribute not found
        self.assertEqual(
            self.run_function('xattr.read', [TEST_FILE, 'patrick']),
            'ERROR: Attribute not found: patrick')

    def test_delete(self):
        '''
        Test xattr.delete
        '''
        # Clear existing attributes
        self.assertTrue(self.run_function('xattr.clear', [TEST_FILE]))

        # Write some attributes
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'spongebob', 'squarepants']))
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'squidward', 'plankton']))
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'crabby', 'patty']))

        # Delete an attribute
        self.assertTrue(
            self.run_function('xattr.delete', [TEST_FILE, 'squidward']))

        # Make sure it was actually deleted
        self.assertEqual(
            self.run_function('xattr.list', [TEST_FILE]),
            {'spongebob': 'squarepants', 'crabby': 'patty'})

        # Test file not found
        self.assertEqual(
            self.run_function('xattr.delete', [NO_FILE, 'spongebob']),
            'ERROR: File not found: {0}'.format(NO_FILE))

        # Test attribute not found
        self.assertEqual(
            self.run_function('xattr.delete', [TEST_FILE, 'patrick']),
            'ERROR: Attribute not found: patrick')

    def test_clear(self):
        '''
        Test xattr.clear
        '''
        # Clear existing attributes
        self.assertTrue(self.run_function('xattr.clear', [TEST_FILE]))

        # Write some attributes
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'spongebob', 'squarepants']))
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'squidward', 'plankton']))
        self.assertTrue(
            self.run_function('xattr.write',
                              [TEST_FILE, 'crabby', 'patty']))

        # Test Clear
        self.assertTrue(self.run_function('xattr.clear', [TEST_FILE]))

        # Test file not found
        self.assertEqual(self.run_function('xattr.clear', [NO_FILE]),
                         'ERROR: File not found: {0}'.format(NO_FILE))
