'''
    :codeauthor: Mike Wiebe <@mikewiebe>
'''

# Copyright (c) 2019 Cisco and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

from tests.unit.modules.nxos.nxos_show_cmd_output import (
    n9k_show_ver,
    n9k_show_ver_list)
from tests.unit.modules.nxos.nxos_grains import (
    n9k_grains)

from salt.exceptions import CommandExecutionError

import salt.proxy.nxos as nxos_proxy


class NxosNxapiProxyTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            nxos_proxy: {
                '__opts__': {
                    'proxy': {
                        'proxytype': 'nxos',
                        'connection': 'nxapi',
                        'host': 'dt-n9k5-1.cisco.com',
                        'username': 'admin',
                        'password': 'password',
                        'prompt_name': 'n9k-device',
                        'ssh_args': '-o PubkeyAuthentication=no',
                        'key_accept': True,
                        'transport': 'https', 'port': 443,
                        'verify': False,
                        'no_save_config': True
                    }
                }
            }
        }

    @staticmethod
    def test_check_virtual():

        """ UT: nxos module:check_virtual method - return value """

        result = nxos_proxy.__virtual__()
        assert 'nxos' in result

    def test_init(self):

        """ UT: nxos module:init method - nxapi proxy """

        with patch.object(nxos_proxy, '_init_nxapi', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.init()

            self.assertTrue(result)

    def test_init_opts_none(self):

        """ UT: nxos module:init method - __opts__ connection is None """

        nxos_proxy.__opts__['proxy']['connection'] = None
        nxos_proxy.CONNECTION = 'nxapi'

        with patch.object(nxos_proxy, '_init_nxapi', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.init()

            self.assertTrue(result)

    def test_init_bad_connection_type(self):

        """ UT: nxos module:init method - bad CONNECTION type """

        nxos_proxy.__opts__['proxy']['connection'] = 'unknown'

        # Execute the function under test
        self.assertFalse(nxos_proxy.init())

    def test_initialized(self):

        """ UT: nxos module:initialized method - nxapi proxy """

        nxos_proxy.CONNECTION = 'nxapi'
        with patch.object(nxos_proxy, '_initialized_nxapi', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.initialized()

            self.assertTrue(result)

    def test_ping(self):

        """ UT: nxos module:ping method - nxapi proxy """

        nxos_proxy.CONNECTION = 'nxapi'
        with patch.object(nxos_proxy, '_ping_nxapi', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.ping()

            self.assertTrue(result)

    def test_grains(self):

        """ UT: nxos module:grains method - nxapi grains """

        kwargs = {}
        nxos_proxy.CONNECTION = 'nxapi'
        with patch.object(nxos_proxy, 'sendline', MagicMock(return_value=n9k_show_ver_list)):

            # Execute the function under test
            result = nxos_proxy.grains(**kwargs)

            self.assertEqual(result, n9k_grains)

    def test_grains_cache_set(self):

        """ UT: nxos module:grains method - nxapi grains cache set """

        kwargs = {}
        nxos_proxy.CONNECTION = 'nxapi'
        nxos_proxy.DEVICE_DETAILS['grains_cache'] = n9k_grains['nxos']
        with patch.object(nxos_proxy, 'sendline', MagicMock(return_value=n9k_show_ver_list)):

            # Execute the function under test
            result = nxos_proxy.grains(**kwargs)

            self.assertEqual(result, n9k_grains)

    def test_grains_refresh(self):

        """ UT: nxos module:grains_refresh method - nxapi grains """

        kwargs = {}
        with patch.object(nxos_proxy, 'grains', MagicMock(return_value=n9k_grains)):

            # Execute the function under test
            result = nxos_proxy.grains_refresh(**kwargs)

            self.assertEqual(result, n9k_grains)

    def test_sendline(self):

        """ UT: nxos module:sendline method - nxapi """

        kwargs = {}
        command = 'show version'

        with patch.object(nxos_proxy, '_nxapi_request', MagicMock(return_value=n9k_show_ver_list)):

            # Execute the function under test
            result = nxos_proxy.sendline(command, **kwargs)

            self.assertEqual(result, n9k_show_ver_list)

    def test_proxy_config(self):

        """ UT: nxos module:proxy_config method - nxapi success path"""

        kwargs = {}
        nxos_proxy.DEVICE_DETAILS['no_save_config'] = True
        commands = ['feature bgp', 'router bgp 65535']

        with patch.object(nxos_proxy, '_nxapi_request', MagicMock(return_value=[{}])):

            # Execute the function under test
            result = nxos_proxy.proxy_config(commands, **kwargs)

            self.assertEqual(result[0], ['feature bgp', 'router bgp 65535'])
            self.assertEqual(result[1], [{}])

    def test_proxy_config_no_save_config(self):

        """ UT: nxos module:proxy_config method - nxapi success path"""

        kwargs = {'no_save_config': False}
        nxos_proxy.DEVICE_DETAILS['no_save_config'] = None
        commands = ['feature bgp', 'router bgp 65535']

        with patch.object(nxos_proxy, '_nxapi_request', MagicMock(return_value=[{}])):
            with patch.object(nxos_proxy, '_nxapi_request', MagicMock(return_value=[{}])):

                # Execute the function under test
                result = nxos_proxy.proxy_config(commands, **kwargs)

                self.assertEqual(result[0], ['feature bgp', 'router bgp 65535'])
                self.assertEqual(result[1], [{}])

    def test__init_nxapi(self):

        """ UT: nxos module:_init_nxapi method - successful connectinon """

        opts = nxos_proxy.__opts__

        with patch.dict(nxos_proxy.__utils__, {'nxos.nxapi_request': MagicMock(return_value='data')}):

            result = nxos_proxy._init_nxapi(opts)

            self.assertTrue(nxos_proxy.DEVICE_DETAILS['initialized'])
            self.assertTrue(nxos_proxy.DEVICE_DETAILS['up'])
            self.assertTrue(nxos_proxy.DEVICE_DETAILS['no_save_config'])
            self.assertTrue(result)

    def test__initialized_nxapi(self):

        """ UT: nxos module:_initialized_nxapi method """
        nxos_proxy.DEVICE_DETAILS['initialized'] = True
        result = nxos_proxy._initialized_nxapi()
        self.assertTrue(result)

        del nxos_proxy.DEVICE_DETAILS['initialized']
        result = nxos_proxy._initialized_nxapi()
        self.assertFalse(result)

    def test__ping_nxapi(self):

        """ UT: nxos module:_ping_nxapi method """
        nxos_proxy.DEVICE_DETAILS['up'] = True
        result = nxos_proxy._ping_nxapi()
        self.assertTrue(result)

        del nxos_proxy.DEVICE_DETAILS['up']
        result = nxos_proxy._ping_nxapi()
        self.assertFalse(result)

    def test__shutdown_nxapi(self):

        """ UT: nxos module:_shutdown_nxapi method """

        opts = {'id': 'value'}
        nxos_proxy._shutdown_nxapi(opts)

    def test__nxapi_request_ssh_return(self):

        """ UT: nxos module:_nxapi_request method - CONNECTION == 'ssh' """

        nxos_proxy.CONNECTION = 'ssh'
        commands = 'show version'
        kwargs = {}

        result = nxos_proxy._nxapi_request(commands, **kwargs)
        self.assertEqual('_nxapi_request is not available for ssh proxy', result)

    def test__nxapi_request_connect(self):

        """ UT: nxos module:_nxapi_request method """

        nxos_proxy.CONNECTION = 'nxapi'
        commands = 'show version'
        kwargs = {}

        with patch.dict(nxos_proxy.__utils__, {'nxos.nxapi_request': MagicMock(return_value='data')}):
            result = nxos_proxy._nxapi_request(commands, **kwargs)
            self.assertEqual('data', result)


class NxosSSHProxyTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            nxos_proxy: {
                '__opts__': {
                    'proxy': {
                        'proxytype': 'nxos',
                        'connection': 'ssh',
                        'host': 'dt-n9k5-1.cisco.com',
                        'username': 'admin',
                        'password': 'password',
                        'prompt_name': 'n9k-device',
                        'ssh_args': '-o PubkeyAuthentication=no',
                        'key_accept': True,
                        'transport': 'https', 'port': 443,
                        'verify': False,
                        'no_save_config': True
                    }
                }
            }
        }

    def test_init(self):

        """ UT: nxos module:init method - ssh proxy """

        with patch.object(nxos_proxy, '_init_ssh', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.init()

            self.assertTrue(result)

    def test_init_opts_none(self):

        """ UT: nxos module:init method - __opts__ connection is None """

        nxos_proxy.__opts__['proxy']['connection'] = None
        nxos_proxy.CONNECTION = 'ssh'

        with patch.object(nxos_proxy, '_init_ssh', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.init()

            self.assertTrue(result)

    def test_initialized(self):

        """ UT: nxos module:initialized method - ssh proxy """

        nxos_proxy.CONNECTION = 'ssh'
        with patch.object(nxos_proxy, '_initialized_ssh', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.initialized()

            self.assertTrue(result)

    def test_ping(self):

        """ UT: nxos module:ping method - ssh proxy """

        nxos_proxy.CONNECTION = 'ssh'
        with patch.object(nxos_proxy, '_ping_ssh', MagicMock(return_value=True)):

            # Execute the function under test
            result = nxos_proxy.ping()

            self.assertTrue(result)

    def test_grains(self):

        """ UT: nxos module:grains method - ssh grains """

        kwargs = {}
        nxos_proxy.CONNECTION = 'ssh'
        with patch.object(nxos_proxy, 'sendline', MagicMock(return_value=n9k_show_ver_list[0])):

            # Execute the function under test
            result = nxos_proxy.grains(**kwargs)

            self.assertEqual(result, n9k_grains)

    def test_sendline(self):

        """ UT: nxos module:sendline method - nxapi """

        kwargs = {}
        command = 'show version'

        with patch.object(nxos_proxy, '_sendline_ssh', MagicMock(return_value=n9k_show_ver_list[0])):

            # Execute the function under test
            result = nxos_proxy.sendline(command, **kwargs)

            self.assertEqual(result, n9k_show_ver_list[0])

    def test_proxy_config(self):

        """ UT: nxos module:proxy_config method - ssh success path """

        kwargs = {}
        nxos_proxy.DEVICE_DETAILS['no_save_config'] = True
        commands = ['feature bgp', 'router bgp 65535']

        with patch.object(nxos_proxy, '_sendline_ssh', MagicMock(return_value='')):
            with patch.object(nxos_proxy, '_sendline_ssh', MagicMock(return_value='')):

                # Execute the function under test
                result = nxos_proxy.proxy_config(commands, **kwargs)

                self.assertEqual(result[0], ['feature bgp', 'router bgp 65535'])
                self.assertEqual(result[1], '')

    def test_proxy_config_no_save_config(self):

        """ UT: nxos module:proxy_config method - ssh success path """

        kwargs = {'no_save_config': False}
        nxos_proxy.DEVICE_DETAILS['no_save_config'] = None
        commands = ['feature bgp', 'router bgp 65535']

        with patch.object(nxos_proxy, '_sendline_ssh', MagicMock(return_value='')):
            with patch.object(nxos_proxy, '_sendline_ssh', MagicMock(return_value='')):
                with patch.object(nxos_proxy, '_sendline_ssh', MagicMock(return_value='')):

                    # Execute the function under test
                    result = nxos_proxy.proxy_config(commands, **kwargs)

                    self.assertEqual(result[0], ['feature bgp', 'router bgp 65535'])
                    self.assertEqual(result[1], '')

    def test_proxy_config_error(self):

        """ UT: nxos module:proxy_config method - CommandExecutionError """

        kwargs = {'no_save_config': False}

        with patch.object(nxos_proxy, '_sendline_ssh', MagicMock(return_value='')) as get_mock:
            with self.assertRaises(CommandExecutionError) as einfo:
                get_mock.side_effect = CommandExecutionError
                nxos_proxy.proxy_config('show version', **kwargs)

    def test__init_ssh(self):

        """ UT: nxos module:_init_ssh method - successful connectinon """

        opts = None

        class _worker_name():
            def __init__(self):
                self.connected = True
                self.name = 'Process-1'

            def sendline(self, command):
                return ['', '']

        with patch.object(nxos_proxy, 'SSHConnection', MagicMock(return_value=_worker_name())):

            nxos_proxy._init_ssh(opts)

            self.assertTrue(nxos_proxy.DEVICE_DETAILS['initialized'])
            self.assertTrue(nxos_proxy.DEVICE_DETAILS['no_save_config'])

    def test__init_ssh_prompt_regex(self):

        """ UT: nxos module:_init_ssh method - prompt regex """

        nxos_proxy.__opts__['proxy']['prompt_regex'] = 'n9k.*device'

        opts = None

        class _worker_name():
            def __init__(self):
                self.connected = True
                self.name = 'Process-1'

            def sendline(self, command):
                return ['', '']

        with patch.object(nxos_proxy, 'SSHConnection', MagicMock(return_value=_worker_name())):

            nxos_proxy._init_ssh(opts)

            self.assertTrue(nxos_proxy.DEVICE_DETAILS['initialized'])
            self.assertTrue(nxos_proxy.DEVICE_DETAILS['no_save_config'])

    def test__init_ssh_no_prompt(self):

        """ UT: nxos module:_init_ssh method - prompt regex """

        del nxos_proxy.__opts__['proxy']['prompt_name']

        opts = nxos_proxy.__opts__

        class _worker_name():
            def __init__(self):
                self.connected = True
                self.name = 'Process-1'

            def sendline(self, command):
                return ['', '']

        with patch.object(nxos_proxy, 'SSHConnection', MagicMock(return_value=_worker_name())):

            nxos_proxy._init_ssh(opts)

            self.assertTrue(nxos_proxy.DEVICE_DETAILS['initialized'])
            self.assertTrue(nxos_proxy.DEVICE_DETAILS['no_save_config'])

    def test__initialized_ssh(self):

        """ UT: nxos module:_initialized_ssh method """
        nxos_proxy.DEVICE_DETAILS['initialized'] = True
        result = nxos_proxy._initialized_ssh()
        self.assertTrue(result)

        del nxos_proxy.DEVICE_DETAILS['initialized']
        result = nxos_proxy._initialized_ssh()
        self.assertFalse(result)

    def test__parse_output_for_errors(self):

        """ UT: nxos module:_parse_output_for_errors method """

        data = "% Incomplete command at '^' marker."
        command = 'show'
        kwargs = {'error_pattern': 'Incomplete'}

        with self.assertRaises(CommandExecutionError) as errinfo:
            nxos_proxy._parse_output_for_errors(data, command, **kwargs)

        data = "% Incomplete command at '^' marker."
        command = 'show'
        kwargs = {'error_pattern': ['Incomplete', 'marker']}

        with self.assertRaises(CommandExecutionError) as errinfo:
            nxos_proxy._parse_output_for_errors(data, command, **kwargs)

        data = "% Invalid command at '^' marker."
        command = 'show bep'
        kwargs = {}

        with self.assertRaises(CommandExecutionError):
            nxos_proxy._parse_output_for_errors(data, command, **kwargs)

        data = "% Incomplete command at '^' marker."
        command = 'show'
        kwargs = {}

        nxos_proxy._parse_output_for_errors(data, command, **kwargs)

        data = "% Incomplete command at '^' marker."
        command = 'show'
        kwargs = {'error_pattern': 'foo'}

        result = nxos_proxy._parse_output_for_errors(data, command, **kwargs)

    def test__init_ssh_raise_exception(self):

        """ UT: nxos module:_init_ssh method - raise exception """

        # NOTE: This test causes problems when debuggin with pdb so comment it
        # out when you need to use pdb.

        del nxos_proxy.__opts__['proxy']['prompt_name']

        opts = None

        class _worker_name():
            def __init__(self):
                self.connected = True
                self.name = 'Process-1'

            def sendline(self, command):
                return ['', '']

        with patch.object(nxos_proxy, 'SSHConnection', MagicMock(return_value=_worker_name())) as get_mock:
            with self.assertRaises(SystemExit) as sys_info:
                with self.assertRaises(Exception) as ex_info:
                    get_mock.side_effect = Exception
                    nxos_proxy._init_ssh(opts)
