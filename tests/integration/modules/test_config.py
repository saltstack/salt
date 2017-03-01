# -*- coding: utf-8 -*-

'''
Validate the config system
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


class ConfigTest(integration.ModuleCase):
    '''
    Test config routines
    '''
    def test_valid_file_proto(self):
        '''
        test config.valid_file_proto
        '''
        self.assertTrue(
            self.run_function('config.valid_fileproto', ['salt://']))
        self.assertTrue(
            self.run_function('config.valid_fileproto', ['http://']))
        self.assertTrue(
            self.run_function('config.valid_fileproto', ['https://']))
        self.assertTrue(
            self.run_function('config.valid_fileproto', ['ftp://']))
        self.assertFalse(
            self.run_function('config.valid_fileproto', ['cheese://']))

    def test_backup_mode(self):
        '''
        test config.backup_mode
        '''
        self.assertEqual(
            self.run_function('config.backup_mode', ['minion']), 'minion')

    def test_manage_mode(self):
        '''
        test config.manage_mode
        '''
        # This function is generally only used with cross calls, the yaml
        # interpreter is breaking it for remote calls
        # The correct standard is the four digit form.
        self.assertEqual(
            self.run_function('config.manage_mode', ['"775"']), '0775')
        self.assertEqual(
            self.run_function('config.manage_mode', ['"1775"']), '1775')
        self.assertEqual(
            self.run_function('config.manage_mode', ['"0775"']), '0775')
        self.assertEqual(
            self.run_function('config.manage_mode', ['"01775"']), '1775')
        self.assertEqual(
            self.run_function('config.manage_mode', ['"0"']), '0000')
        self.assertEqual(
            self.run_function('config.manage_mode', ['775']), '0775')
        self.assertEqual(
            self.run_function('config.manage_mode', ['1775']), '1775')
        self.assertEqual(
            self.run_function('config.manage_mode', ['0']), '0000')

    def test_option(self):
        '''
        test config.option
        '''
        # Minion opt
        self.assertEqual(
                self.run_function(
                    'config.option',
                    ['master_port']),
                64506)
        # pillar conf opt
        self.assertEqual(
                self.run_function(
                    'config.option',
                    ['ext_spam']),
                'eggs')

    def test_get(self):
        '''
        Test option.get
        '''
        # Check pillar get
        self.assertEqual(
                self.run_function(
                    'config.get',
                    ['level1:level2']),
                'foo')
        # Check master config
        self.assertEqual(
                self.run_function(
                    'config.get',
                    ['config_opt:layer2']),
                'kosher')
        # Check minion config
        self.assertEqual(
                self.run_function(
                    'config.get',
                    ['config_test:spam']),
                'eggs')
