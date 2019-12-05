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
