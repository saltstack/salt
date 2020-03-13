# -*- coding: utf-8 -*-

'''
Validate the config system
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase

import pytest


@pytest.mark.windows_whitelisted
class ConfigTest(ModuleCase):
    '''
    Test config routines
    '''
    def test_valid_file_proto(self):
        '''
        test config.valid_file_proto
        '''
        assert self.run_function('config.valid_fileproto', ['salt://'])
        assert self.run_function('config.valid_fileproto', ['file://'])
        assert self.run_function('config.valid_fileproto', ['http://'])
        assert self.run_function('config.valid_fileproto', ['https://'])
        assert self.run_function('config.valid_fileproto', ['ftp://'])
        assert self.run_function('config.valid_fileproto', ['s3://'])
        assert self.run_function('config.valid_fileproto', ['swift://'])
        assert not self.run_function('config.valid_fileproto', ['cheese://'])

    def test_backup_mode(self):
        '''
        test config.backup_mode
        '''
        assert self.run_function('config.backup_mode', ['minion']) == 'minion'

    def test_manage_mode(self):
        '''
        test config.manage_mode
        '''
        # This function is generally only used with cross calls, the yaml
        # interpreter is breaking it for remote calls
        # The correct standard is the four digit form.
        assert self.run_function('config.manage_mode', ['"775"']) == '0775'
        assert self.run_function('config.manage_mode', ['"1775"']) == '1775'
        assert self.run_function('config.manage_mode', ['"0775"']) == '0775'
        assert self.run_function('config.manage_mode', ['"01775"']) == '1775'
        assert self.run_function('config.manage_mode', ['"0"']) == '0000'
        assert self.run_function('config.manage_mode', ['775']) == '0775'
        assert self.run_function('config.manage_mode', ['1775']) == '1775'
        assert self.run_function('config.manage_mode', ['0']) == '0000'

    def test_option(self):
        '''
        test config.option
        '''
        # Minion opt
        assert self.run_function(
                    'config.option',
                    ['master_port']) == \
                self.get_config('minion')['master_port']
        # pillar conf opt
        assert self.run_function(
                    'config.option',
                    ['ext_spam']) == \
                'eggs'

    def test_get(self):
        '''
        Test option.get
        '''
        # Check pillar get
        assert self.run_function(
                    'config.get',
                    ['level1:level2']) == \
                'foo'
        # Check master config
        assert self.run_function(
                    'config.get',
                    ['config_opt:layer2']) == \
                'kosher'
        # Check minion config
        assert self.run_function(
                    'config.get',
                    ['config_test:spam']) == \
                'eggs'
