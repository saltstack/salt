# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.modules.helm as helm


class HelmTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.helm
    '''
    def setup_loader_modules(self):
        return {helm: {}}


    # _prepare_cmd
    def test__prepare_cmd(self):
        '''
        Test for the command preparation return, without parameters.
        '''
        self.assertEqual(helm._prepare_cmd(),
                         ('helm', ))


    def test__prepare_cmd_binary(self):
        '''
        Test for the command preparation return, with binary.
        '''
        self.assertEqual(helm._prepare_cmd(binary='binary'),
                         ('binary', ))


    def test__prepare_cmd_commands(self):
        '''
        Test for the command preparation return, with commands.
        '''
        self.assertEqual(helm._prepare_cmd(commands=['com1', 'com2']),
                         ('helm', 'com1', 'com2', ))


    def test__prepare_cmd_flags(self):
        '''
        Test for the command preparation return, with flags.
        '''
        self.assertEqual(helm._prepare_cmd(flags=['flag1', '--flag2']),
                         ('helm', '--flag1', '--flag2', ))


    def test__prepare_cmd_kvflags(self):
        '''
        Test for the command preparation return, with kvflags.
        '''
        self.assertEqual(helm._prepare_cmd(kvflags={'kflag1': 'vflag1', '--kflag2': 'vflag2'}),
                         ('helm', '--kflag1', 'vflag1', '--kflag2', 'vflag2', ))


    # _exec_cmd
    def test__exec_cmd_succes(self):
        cmd_prepare = helm._prepare_cmd()
        cmd_prepare_str = ' '.join(cmd_prepare)
        cmd_return = {
            'stdout': "succes",
            'stderr': "",
            'retcode': 0,
        }
        result = cmd_return
        result.update({'cmd': cmd_prepare_str})
        # Test fetching new certificate
        with patch.dict(helm.__salt__, {  # pylint: disable=no-member
                 'cmd.run_all': MagicMock(return_value=cmd_return)
             }):
            self.assertEqual(helm._exec_cmd(), result)