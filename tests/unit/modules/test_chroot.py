# -*- coding: utf-8 -*-
#
# Author: Alberto Planas <aplanas@suse.com>
#
# Copyright 2018 SUSE LINUX GmbH, Nuernberg, Germany.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

'''
:maintainer:    Alberto Planas <aplanas@suse.com>
:platform:      Linux
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import sys

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch,
)

from salt.exceptions import CommandExecutionError
import salt.utils.platform
import salt.modules.chroot as chroot


@skipIf(salt.utils.platform.is_windows(), 'This test cannot work on Windows')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ChrootTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.chroot
    '''

    def setup_loader_modules(self):
        return {
            chroot: {
                '__salt__': {},
                '__utils__': {},
                '__opts__': {'cachedir': ''},
            }
        }

    @patch('os.path.isdir')
    def test_exist(self, isdir):
        '''
        Test if the chroot environment exist.
        '''
        isdir.side_effect = (True, True, True, True)
        self.assertTrue(chroot.exist('/chroot'))

        isdir.side_effect = (True, True, True, False)
        self.assertFalse(chroot.exist('/chroot'))

    @patch('os.makedirs')
    @patch('salt.modules.chroot.exist')
    def test_create(self, exist, makedirs):
        '''
        Test the creation of an empty chroot environment.
        '''
        exist.return_value = True
        self.assertTrue(chroot.create('/chroot'))
        makedirs.assert_not_called()

        exist.return_value = False
        self.assertTrue(chroot.create('/chroot'))
        makedirs.assert_called()

    @patch('salt.modules.chroot.exist')
    def test_call_fails_input_validation(self, exist):
        '''
        Test execution of Salt functions in chroot.
        '''
        # Basic input validation
        exist.return_value = False
        self.assertRaises(CommandExecutionError, chroot.call, '/chroot', '')
        self.assertRaises(CommandExecutionError, chroot.call, '/chroot',
                          'test.ping')

    @patch('salt.modules.chroot.exist')
    @patch('tempfile.mkdtemp')
    def test_call_fails_untar(self, mkdtemp, exist):
        '''
        Test execution of Salt functions in chroot.
        '''
        # Fail the tar command
        exist.return_value = True
        mkdtemp.return_value = '/chroot/tmp01'
        utils_mock = {
            'thin.gen_thin': MagicMock(return_value='/salt-thin.tgz'),
            'files.rm_rf': MagicMock(),
        }
        salt_mock = {
            'cmd.run': MagicMock(return_value='Error'),
            'config.option': MagicMock(),
        }
        with patch.dict(chroot.__utils__, utils_mock), \
                patch.dict(chroot.__salt__, salt_mock):
            self.assertEqual(chroot.call('/chroot', 'test.ping'), {
                'result': False,
                'comment': 'Error'
            })
            utils_mock['thin.gen_thin'].assert_called_once()
            salt_mock['config.option'].assert_called()
            salt_mock['cmd.run'].assert_called_once()
            utils_mock['files.rm_rf'].assert_called_once()

    @patch('salt.modules.chroot.exist')
    @patch('tempfile.mkdtemp')
    def test_call_fails_salt_thin(self, mkdtemp, exist):
        '''
        Test execution of Salt functions in chroot.
        '''
        # Fail the inner command
        exist.return_value = True
        mkdtemp.return_value = '/chroot/tmp01'
        utils_mock = {
            'thin.gen_thin': MagicMock(return_value='/salt-thin.tgz'),
            'files.rm_rf': MagicMock(),
            'json.find_json': MagicMock(return_value={'return': {}})
        }
        salt_mock = {
            'cmd.run': MagicMock(return_value=''),
            'config.option': MagicMock(),
            'cmd.run_chroot': MagicMock(return_value={
                'retcode': 1,
                'stderr': 'Error',
            }),
        }
        with patch.dict(chroot.__utils__, utils_mock), \
                patch.dict(chroot.__salt__, salt_mock):
            self.assertEqual(chroot.call('/chroot', 'test.ping'), {
                'result': False,
                'comment': "Can't parse container command output"
            })
            utils_mock['thin.gen_thin'].assert_called_once()
            salt_mock['config.option'].assert_called()
            salt_mock['cmd.run'].assert_called_once()
            salt_mock['cmd.run_chroot'].assert_called_with(
                '/chroot',
                ['python{}'.format(sys.version_info[0]), '/tmp01/salt-call',
                 '--metadata', '--local',
                 '--log-file', '/tmp01/log', '--cachedir', '/tmp01/cache',
                 '--out', 'json', '-l', 'quiet', '--', 'test.ping'])
            utils_mock['files.rm_rf'].assert_called_once()

    @patch('salt.modules.chroot.exist')
    @patch('tempfile.mkdtemp')
    def test_call_success(self, mkdtemp, exist):
        '''
        Test execution of Salt functions in chroot.
        '''
        # Success test
        exist.return_value = True
        mkdtemp.return_value = '/chroot/tmp01'
        utils_mock = {
            'thin.gen_thin': MagicMock(return_value='/salt-thin.tgz'),
            'files.rm_rf': MagicMock(),
            'json.find_json': MagicMock(return_value={'return': 'result'})
        }
        salt_mock = {
            'cmd.run': MagicMock(return_value=''),
            'config.option': MagicMock(),
            'cmd.run_chroot': MagicMock(return_value={
                'retcode': 0,
                'stdout': '',
            }),
        }
        with patch.dict(chroot.__utils__, utils_mock), \
                patch.dict(chroot.__salt__, salt_mock):
            self.assertEqual(chroot.call('/chroot', 'test.ping'), 'result')
            utils_mock['thin.gen_thin'].assert_called_once()
            salt_mock['config.option'].assert_called()
            salt_mock['cmd.run'].assert_called_once()
            salt_mock['cmd.run_chroot'].assert_called_with(
                '/chroot',
                ['python{}'.format(sys.version_info[0]), '/tmp01/salt-call',
                 '--metadata', '--local',
                 '--log-file', '/tmp01/log', '--cachedir', '/tmp01/cache',
                 '--out', 'json', '-l', 'quiet', '--', 'test.ping'])
            utils_mock['files.rm_rf'].assert_called_once()

    @patch('salt.modules.chroot.exist')
    @patch('tempfile.mkdtemp')
    def test_call_success_parameters(self, mkdtemp, exist):
        '''
        Test execution of Salt functions in chroot with parameters.
        '''
        # Success test
        exist.return_value = True
        mkdtemp.return_value = '/chroot/tmp01'
        utils_mock = {
            'thin.gen_thin': MagicMock(return_value='/salt-thin.tgz'),
            'files.rm_rf': MagicMock(),
            'json.find_json': MagicMock(return_value={'return': 'result'})
        }
        salt_mock = {
            'cmd.run': MagicMock(return_value=''),
            'config.option': MagicMock(),
            'cmd.run_chroot': MagicMock(return_value={
                'retcode': 0,
                'stdout': '',
            }),
        }
        with patch.dict(chroot.__utils__, utils_mock), \
                patch.dict(chroot.__salt__, salt_mock):
            self.assertEqual(chroot.call('/chroot', 'module.function',
                                         key='value'), 'result')
            utils_mock['thin.gen_thin'].assert_called_once()
            salt_mock['config.option'].assert_called()
            salt_mock['cmd.run'].assert_called_once()
            salt_mock['cmd.run_chroot'].assert_called_with(
                '/chroot',
                ['python{}'.format(sys.version_info[0]), '/tmp01/salt-call',
                 '--metadata', '--local',
                 '--log-file', '/tmp01/log', '--cachedir', '/tmp01/cache',
                 '--out', 'json', '-l', 'quiet',
                 '--', 'module.function', 'key=value'])
            utils_mock['files.rm_rf'].assert_called_once()

    @patch('salt.modules.chroot._create_and_execute_salt_state')
    @patch('salt.client.ssh.state.SSHHighState')
    @patch('salt.fileclient.get_file_client')
    @patch('salt.utils.state.get_sls_opts')
    def test_sls(self, get_sls_opts, get_file_client, SSHHighState,
                 _create_and_execute_salt_state):
        '''
        Test execution of Salt states in chroot.
        '''
        SSHHighState.return_value = SSHHighState
        SSHHighState.render_highstate.return_value = (None, [])
        SSHHighState.state.reconcile_extend.return_value = (None, [])
        SSHHighState.state.requisite_in.return_value = (None, [])
        SSHHighState.state.verify_high.return_value = []

        _create_and_execute_salt_state.return_value = 'result'
        opts_mock = {
            'hash_type': 'md5',
        }
        get_sls_opts.return_value = opts_mock
        with patch.dict(chroot.__opts__, opts_mock):
            self.assertEqual(chroot.sls('/chroot', 'module'), 'result')
            _create_and_execute_salt_state.assert_called_once()

    @patch('salt.modules.chroot._create_and_execute_salt_state')
    @patch('salt.client.ssh.state.SSHHighState')
    @patch('salt.fileclient.get_file_client')
    @patch('salt.utils.state.get_sls_opts')
    def test_highstate(self, get_sls_opts, get_file_client, SSHHighState,
                       _create_and_execute_salt_state):
        '''
        Test execution of Salt states in chroot.
        '''
        SSHHighState.return_value = SSHHighState

        _create_and_execute_salt_state.return_value = 'result'
        opts_mock = {
            'hash_type': 'md5',
        }
        get_sls_opts.return_value = opts_mock
        with patch.dict(chroot.__opts__, opts_mock):
            self.assertEqual(chroot.highstate('/chroot'), 'result')
            _create_and_execute_salt_state.assert_called_once()
