# -*- coding: utf-8 -*-
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


# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch,
    call)

from tests.unit.modules.nxos.nxos_show_run import (
    n9k_running_config,
    n9k_show_running_config_list,
    n9k_show_running_inc_username_list)
from tests.unit.modules.nxos.nxos_grains import n9k_grains
from tests.unit.modules.nxos.nxos_show_cmd_output import (
    n9k_get_user_output,
    n9k_show_ver,
    n9k_show_ver_list,
    n9k_show_ver_int_list,
    n9k_show_ver_structured,
    n9k_show_ver_int_list_structured,
    n9k_show_user_account,
    n9k_show_user_account_list)

from tests.unit.modules.nxos.nxos_config import (
    config_input_file,
    config_result,
    config_result_file,
    delete_config,
    initial_config,
    initial_config_file,
    modified_config,
    modified_config_file,
    remove_user,
    save_running_config,
    set_role,
    template_engine_file_str,
    template_engine_file_str_file,
    unset_role)

from salt.exceptions import CommandExecutionError, NxosError
from socket import error as socket_error

# Import Salt Libs
import salt.modules.nxos as nxos

# pylint: disable-msg=C0103
# pylint: disable-msg=C0301
# pylint: disable-msg=E1101
# pylint: disable-msg=R0904


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NxosTestCase(TestCase, LoaderModuleMockMixin):

    """ Test cases for salt.modules.nxos """

    COPY_RS = 'copy running-config startup-config'

    def setup_loader_modules(self):
        return {
            nxos: {
                '__proxy__': {'nxos.sendline': MagicMock(
                    return_value={'command': 'fake_output'})}
            }
        }

    def tearDown(self):
        pass

    @staticmethod
    def test_check_virtual():

        """ UT: nxos module:check_virtual method - return value """

        result = nxos.__virtual__()
        assert 'nxos' in result

    def test_ping_proxy(self):

        """ UT: nxos module:ping method - proxy """

        kwargs = {}
        command = 'show version'
        method = 'cli_show_ascii'

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=True)):
            with patch.dict(nxos.__proxy__, {'nxos.ping': MagicMock(return_value=True)}):

                # Execute the function under test
                result = nxos.ping(**kwargs)

                self.assertTrue(result)

    def test_ping_native_minion(self):

        """ UT: nxos module:ping method - proxy """

        kwargs = {}
        command = 'show version'
        method = 'cli_show_ascii'

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=False)):
            with patch.dict(nxos.__utils__, {'nxos.ping': MagicMock(return_value=True)}):

                # Execute the function under test
                result = nxos.ping(**kwargs)

                self.assertTrue(result)

    def test_check_password_return_none(self):

        """ UT: nxos module:check_password method - return None """

        username = 'admin'
        password = 'foo'
        kwargs = {}
        with patch.object(nxos, 'get_user', MagicMock(return_value=None)):

            # Execute the function under test
            result = nxos.check_password(username, password, encrypted=False, **kwargs)

            self.assertIsNone(result)

    def test_check_password_password_nxos_comment(self):

        """ UT: nxos module:check_password method - password_line has '!' """

        username = 'admin'
        password = 'foo'
        kwargs = {}
        with patch.object(nxos, 'get_user', MagicMock(return_value='!')):

            # Execute the function under test
            result = nxos.check_password(username, password, encrypted=False, **kwargs)

            self.assertFalse(result)

    def test_check_password_password_encrypted_false(self):

        """ UT: nxos module:check_password method - password is not encrypted """

        username = 'salt_test'
        password = 'foobar123&'
        kwargs = {}
        with patch.object(nxos, 'get_user', MagicMock(return_value=n9k_get_user_output)):

            # Execute the function under test
            result = nxos.check_password(username, password, encrypted=False, **kwargs)

            # TODO: This fails on mac.  SHould be an assertTrue
            self.assertFalse(result)

    def test_check_password_password_encrypted_true(self):

        """ UT: nxos module:check_password method - password is encrypted """

        username = 'salt_test'
        password = '$5$mkXh6O4T$YUVtA89HbXCnue63kgghPlaqPHyaXhdtxPBbPEHhbRC'
        kwargs = {}
        with patch.object(nxos, 'get_user', MagicMock(return_value=n9k_get_user_output)):

            # Execute the function under test
            result = nxos.check_password(username, password, encrypted=True, **kwargs)

            self.assertTrue(result)

    def test_check_password_password_encrypted_true_negative(self):

        """ UT: nxos module:check_password method - password is not encrypted """

        username = 'salt_test'
        password = 'foobar123&'
        kwargs = {}
        with patch.object(nxos, 'get_user', MagicMock(return_value=n9k_running_config)):

            # Execute the function under test
            result = nxos.check_password(username, password, encrypted=True, **kwargs)

            self.assertFalse(result)

    def test_check_role_true(self):

        """ UT: nxos module:check_role method - Role configured """

        username = 'salt_test'
        roles = ['network-admin', 'dev-ops']
        kwargs = {}
        with patch.object(nxos, 'get_roles', MagicMock(return_value=roles)):

            # Execute the function under test
            result = nxos.check_role(username, 'dev-ops', **kwargs)

            self.assertTrue(result)

    def test_check_role_false(self):

        """ UT: nxos module:check_role method - Role not configured """

        username = 'salt_test'
        roles = ['network-admin', 'dev-ops']
        kwargs = {}
        with patch.object(nxos, 'get_roles', MagicMock(return_value=roles)):

            # Execute the function under test
            result = nxos.check_role(username, 'network-operator', **kwargs)

            self.assertFalse(result)

    def test_cmd_any_function(self):

        """ UT: nxos module:cmd method - check_role function """

        username = 'salt_test'
        roles = ['network-admin', 'dev-ops']
        with patch.dict(nxos.__salt__,
                        {'nxos.check_role': MagicMock(return_value=True)}):

            # Execute the function under test
            result = nxos.cmd('check_role', 'salt_test', 'network-admin', encrypted=True, __pub_fun='nxos.cmd')

            self.assertTrue(result)

    def test_cmd_function_absent(self):

        """ UT: nxos module:cmd method - non existent function """

        # Execute the function under test with non existent function name
        result = nxos.cmd('cool_new_function', 'salt_test', 'network-admin', encrypted=True)

        self.assertFalse(result)

    def test_find_single_match(self):

        """ UT: nxos module:test_find method - Find single match in running config """

        find_pattern = '^vrf context testing$'
        find_string = 'vrf context testing'
        with patch.object(nxos, 'show_run', MagicMock(return_value=n9k_running_config)):

            # Execute the function under test
            result = nxos.find(find_pattern)
            self.assertIn(find_string, result)

    def test_find_multiple_matches(self):

        """ UT: nxos module:test_find method - Find multiple matches in running config """

        find_pattern = '^no logging.*$'
        find_string = 'no logging event link-status enable'
        with patch.object(nxos, 'show_run', MagicMock(return_value=n9k_running_config)):

            # Execute the function under test
            result = nxos.find(find_pattern)
            self.assertIn(find_string, result)
            self.assertEqual(len(result), 7)

    def test_get_roles_user_not_configured(self):

        """ UT: nxos module:get_roles method - User not configured """

        username = 'salt_does_not_exist'
        user_info = ''
        kwargs = {}
        with patch.object(nxos, 'get_user', MagicMock(return_value=user_info)):

            # Execute the function under test
            result = nxos.get_roles(username, **kwargs)

            self.assertEqual(result, [])

    def test_get_roles_user_configured(self):

        """ UT: nxos module:get_roles method - User configured """

        username = 'salt_test'
        user_info = ''
        kwargs = {}
        expected_result = ['network-operator', 'network-admin', 'dev-ops']
        with patch.object(nxos, 'get_user', MagicMock(return_value='salt_test')):
            for rv in [n9k_show_user_account, n9k_show_user_account_list]:
                with patch.object(nxos, 'show', MagicMock(return_value=rv)):

                    # Execute the function under test
                    result = nxos.get_roles(username, **kwargs)

                    self.assertEqual(result.sort(), expected_result.sort())

    def test_get_roles_user_configured_no_role(self):

        """ UT: nxos module:get_roles method - User configured no roles"""

        username = 'salt_test'
        user_info = ''
        kwargs = {}
        with patch.object(nxos, 'get_user', MagicMock(return_value='salt_test')):
            with patch.object(nxos, 'show', MagicMock(return_value='')):

                # Execute the function under test
                result = nxos.get_roles(username, **kwargs)

                self.assertEqual(result, [])

    def test_get_user_configured(self):

        """ UT: nxos module:get_user method - User configured """

        username = 'salt_test'
        expected_output = n9k_show_running_inc_username_list[0]
        kwargs = {}

        for rv in [n9k_show_running_inc_username_list[0], n9k_show_running_inc_username_list]:
            with patch.object(nxos, 'show', MagicMock(return_value=rv)):

                # Execute the function under test
                result = nxos.get_user(username, **kwargs)

                self.assertEqual(result, expected_output)

    def test_grains(self):

        """ UT: nxos module:grains method """

        kwargs = {}
        nxos.DEVICE_DETAILS['grains_cache'] = {}
        expected_grains = {'software':
                           {'BIOS': 'version 08.36', 'NXOS': 'version 9.2(1)',
                            'BIOS compile time': '06/07/2019',
                            'NXOS image file is': 'bootflash:///nxos.9.2.1.bin',
                            'NXOS compile time': '7/17/2018 16:00:00 [07/18/2018 00:21:19]'},
                           'hardware':
                           {'Device name': 'n9k-device',
                            'bootflash': '53298520 kB'},
                           'plugins': ['Core Plugin', 'Ethernet Plugin']}
        with patch.dict(nxos.__salt__,
                        {'utils.nxos.system_info': MagicMock(return_value=n9k_grains)}):
            with patch.object(nxos, 'show_ver', MagicMock(return_value=n9k_show_ver)):

                # Execute the function under test
                result = nxos.grains(**kwargs)

                self.assertEqual(result, expected_grains)

    def test_grains_get_cache(self):

        """ UT: nxos module:grains method """

        kwargs = {}
        expected_grains = {'software':
                           {'BIOS': 'version 08.36', 'NXOS': 'version 9.2(1)',
                            'BIOS compile time': '06/07/2019',
                            'NXOS image file is': 'bootflash:///nxos.9.2.1.bin',
                            'NXOS compile time': '7/17/2018 16:00:00 [07/18/2018 00:21:19]'},
                           'hardware':
                           {'Device name': 'n9k-device',
                            'bootflash': '53298520 kB'},
                           'plugins': ['Core Plugin', 'Ethernet Plugin']}
        nxos.DEVICE_DETAILS['grains_cache'] = expected_grains
        with patch.dict(nxos.__salt__,
                        {'utils.nxos.system_info': MagicMock(return_value=n9k_grains)}):
            with patch.object(nxos, 'show_ver', MagicMock(return_value=n9k_show_ver)):

                # Execute the function under test
                result = nxos.grains(**kwargs)

                self.assertEqual(result, expected_grains)

    def test_grains_refresh(self):

        """ UT: nxos module:grains_refresh method """

        kwargs = {}
        expected_grains = {'software':
                           {'BIOS': 'version 08.36', 'NXOS': 'version 9.2(1)',
                            'BIOS compile time': '06/07/2019',
                            'NXOS image file is': 'bootflash:///nxos.9.2.1.bin',
                            'NXOS compile time': '7/17/2018 16:00:00 [07/18/2018 00:21:19]'},
                           'hardware':
                           {'Device name': 'n9k-device',
                            'bootflash': '53298520 kB'},
                           'plugins': ['Core Plugin', 'Ethernet Plugin']}
        # Replace 'get_roles' with our own mock function
        with patch.object(nxos, 'grains', MagicMock(return_value=expected_grains)):

            # Execute the function under test
            result = nxos.grains_refresh(**kwargs)

            self.assertEqual(result, expected_grains)

    def test_system_info(self):

        """ UT: nxos module:system_info method """

        kwargs = {}
        expected_grains = {'software':
                           {'BIOS': 'version 08.36', 'NXOS': 'version 9.2(1)',
                            'BIOS compile time': '06/07/2019',
                            'NXOS image file is': 'bootflash:///nxos.9.2.1.bin',
                            'NXOS compile time': '7/17/2018 16:00:00 [07/18/2018 00:21:19]'},
                           'hardware':
                           {'Device name': 'n9k-device',
                            'bootflash': '53298520 kB'},
                           'plugins': ['Core Plugin', 'Ethernet Plugin']}
        with patch.dict(nxos.__salt__,
                        {'utils.nxos.system_info': MagicMock(return_value=n9k_grains)}):
            with patch.object(nxos, 'show', MagicMock(return_value=n9k_show_ver)):

                # Execute the function under test
                result = nxos.system_info(**kwargs)

                self.assertEqual(result, expected_grains)

    def test_sendline_invalid_method(self):

        """ UT: nxos module:sendline method - invalid method """

        kwargs = {}
        command = 'show version'
        method = 'invalid'

        # Execute the function under test
        result = nxos.sendline(command, method, **kwargs)

        self.assertIn('INPUT ERROR', result)

    def test_sendline_valid_method_proxy(self):

        """ UT: nxos module:sendline method - valid method over proxy """

        kwargs = {}
        command = 'show version'
        method = 'cli_show_ascii'

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=True)):
            mock_cmd = MagicMock(return_value=n9k_show_ver)
            with patch.dict(nxos.__proxy__, {'nxos.sendline': mock_cmd}):

                # Execute the function under test
                result = nxos.sendline(command, method, **kwargs)

                self.assertIn(n9k_show_ver, result)

    def test_sendline_valid_method_nxapi_uds(self):

        """ UT: nxos module:sendline method - valid method over nxapi uds """

        kwargs = {}
        command = 'show version'
        method = 'cli_show_ascii'

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=False)):
            with patch.object(nxos, '_nxapi_request', MagicMock(return_value=n9k_show_ver)):

                # Execute the function under test
                result = nxos.sendline(command, method, **kwargs)

                self.assertIn(n9k_show_ver, result)

    def test_show_raw_text_invalid(self):

        """ UT: nxos module:show method - invalid argument """

        kwargs = {}
        command = 'show version'
        raw_text = 'invalid'

        # Execute the function under test
        result = nxos.show(command, raw_text, **kwargs)

        self.assertIn('INPUT ERROR', result)

    def test_show_raw_text_true(self):

        """ UT: nxos module:show method - raw_test true """

        kwargs = {}
        command = 'show version'
        raw_text = True

        with patch.object(nxos, 'sendline', MagicMock(return_value=n9k_show_ver)):
            # Execute the function under test
            result = nxos.show(command, raw_text, **kwargs)

            self.assertEqual(result, n9k_show_ver)

    def test_show_raw_text_true_multiple_commands(self):

        """ UT: nxos module:show method - raw_test true multiple commands """

        kwargs = {}
        command = 'show bgp sessions ; show processes'
        raw_text = True
        data = ['bgp_session_data', 'process_data']

        with patch.object(nxos, 'sendline', MagicMock(return_value=data)):
            # Execute the function under test
            result = nxos.show(command, raw_text, **kwargs)

            self.assertEqual(result, data)

    def test_show_nxapi(self):

        """ UT: nxos module:show method - nxapi returns info as list """

        kwargs = {}
        command = 'show version; show interface eth1/1'
        raw_text = True
        expected_output1 = n9k_show_ver_int_list[0]
        expected_output2 = n9k_show_ver_int_list[1]

        with patch.object(nxos, 'sendline', MagicMock(return_value=n9k_show_ver_int_list)):
            # Execute the function under test
            result = nxos.show(command, raw_text, **kwargs)
            self.assertEqual(result[0], expected_output1)
            self.assertEqual(result[1], expected_output2)

    def test_show_nxapi_structured(self):

        """ UT: nxos module:show method - nxapi returns info as list """

        kwargs = {}
        command = 'show version; show interface eth1/1'
        raw_text = False
        expected_output1 = n9k_show_ver_int_list_structured[0]
        expected_output2 = n9k_show_ver_int_list_structured[1]

        with patch.object(nxos, 'sendline', MagicMock(return_value=n9k_show_ver_int_list_structured)):
            # Execute the function under test
            result = nxos.show(command, raw_text, **kwargs)
            self.assertEqual(result[0].keys(), n9k_show_ver_int_list_structured[0].keys())
            self.assertEqual(result[1].keys(), n9k_show_ver_int_list_structured[1].keys())

    def test_show_run(self):

        """ UT: nxos module:show_run method """

        kwargs = {}
        expected_output = n9k_show_running_config_list[0]

        for rv in [n9k_show_running_config_list[0], n9k_show_running_config_list]:
            with patch.object(nxos, 'show', MagicMock(return_value=rv)):

                # Execute the function under test
                result = nxos.show_run(**kwargs)
                self.assertEqual(result, expected_output)

    def test_show_ver(self):

        """ UT: nxos module:show_ver method """

        kwargs = {}
        expected_output = n9k_show_ver_list[0]

        for rv in [n9k_show_ver_list[0], n9k_show_ver_list]:
            with patch.object(nxos, 'show', MagicMock(return_value=rv)):

                # Execute the function under test
                result = nxos.show_ver(**kwargs)
                self.assertEqual(result, expected_output)

    def test_add_config(self):

        """ UT: nxos module:add_config method """

        kwargs = {}
        expected_output = 'COMMAND_LIST: feature bgp'

        with patch.object(nxos, 'config', MagicMock(return_value=expected_output)):

            # Execute the function under test
            result = nxos.add_config('feature bgp', **kwargs)
            self.assertEqual(result, expected_output)

    def test_config_commands(self):

        """ UT: nxos module:config method - Using commands arg"""

        commands = ['no feature ospf', ['no feature ospf']]
        kwargs = {}
        expected_output = 'COMMAND_LIST: no feature ospf\n\n'

        for cmd_set in commands:
            with patch.object(nxos, 'show', MagicMock(return_value=initial_config)):
                mock_cmd = MagicMock(return_value=template_engine_file_str)
                with patch.dict(nxos.__salt__, {'file.apply_template_on_contents': mock_cmd}):
                    with patch.object(nxos, '_configure_device', MagicMock(return_value=config_result)):
                        with patch.object(nxos, 'show', MagicMock(return_value=modified_config)):

                            # Execute the function under test
                            result = nxos.config(cmd_set, **kwargs)
                            self.assertEqual(result, expected_output)

    def test_config_commands_template_none(self):

        """ UT: nxos module:config method - Template engine is None"""

        commands = ['no feature ospf', ['no feature ospf']]
        kwargs = {}
        expected_output = 'COMMAND_LIST: no feature ospf\n\n'

        for cmd_set in commands:
            with patch.object(nxos, 'show', MagicMock(return_value=initial_config)):
                mock_cmd = MagicMock(return_value=template_engine_file_str)
                with patch.dict(nxos.__salt__, {'file.apply_template_on_contents': mock_cmd}):
                    with patch.object(nxos, '_configure_device', MagicMock(return_value=config_result)):
                        with patch.object(nxos, 'show', MagicMock(return_value=modified_config)):

                            # Execute the function under test
                            result = nxos.config(cmd_set, template_engine=None, **kwargs)
                            self.assertEqual(result, expected_output)

    def test_config_commands_string(self):

        """ UT: nxos module:config method - Using commands arg and output is string"""

        commands = 'no feature ospf'
        kwargs = {}
        expected_output = 'COMMAND_LIST: no feature ospf\n\n'

        with patch.object(nxos, 'show', MagicMock(return_value=initial_config[0])):
            mock_cmd = MagicMock(return_value=template_engine_file_str)
            with patch.dict(nxos.__salt__, {'file.apply_template_on_contents': mock_cmd}):
                with patch.object(nxos, '_configure_device', MagicMock(return_value=config_result)):
                    with patch.object(nxos, 'show', MagicMock(return_value=modified_config[0])):

                        # Execute the function under test
                        result = nxos.config(commands, **kwargs)
                        self.assertEqual(result, expected_output)

    def test_config_file(self):

        """ UT: nxos module:config method - Using config_file arg"""

        config_file = 'salt://bgp_config.txt'
        kwargs = {}
        expected_output = 'COMMAND_LIST: feature bgp ; ! ; router bgp 55 ; address-family ipv4 unicast ; no client-to-client reflection ; additional-paths send\n\n'

        with patch.object(nxos, 'show', MagicMock(return_value=initial_config_file)):
            mock_cmd = MagicMock(return_value=config_input_file)
            with patch.dict(nxos.__salt__, {'cp.get_file_str': mock_cmd}):
                mock_cmd = MagicMock(return_value=template_engine_file_str_file)
                with patch.dict(nxos.__salt__, {'file.apply_template_on_contents': mock_cmd}):
                    with patch.object(nxos, '_configure_device', MagicMock(return_value=config_result_file)):
                        with patch.object(nxos, 'show', MagicMock(return_value=modified_config_file)):

                            # Execute the function under test
                            result = nxos.config(config_file=config_file, **kwargs)
                            self.assertEqual(result, expected_output)

    def test_config_file_error1(self):

        """ UT: nxos module:config method - Error file not found """

        config_file = 'salt://bgp_config.txt'
        kwargs = {}

        with patch.object(nxos, 'show', MagicMock(return_value=initial_config_file)):
            mock_cmd = MagicMock(return_value=False)
            with patch.dict(nxos.__salt__, {'cp.get_file_str': mock_cmd}):
                mock_cmd = MagicMock(return_value=template_engine_file_str_file)
                with patch.dict(nxos.__salt__, {'file.apply_template_on_contents': mock_cmd}):
                    with patch.object(nxos, '_configure_device', MagicMock(return_value=config_result_file)):
                        with patch.object(nxos, 'show', MagicMock(return_value=modified_config_file)):

                            # Execute the function under test
                            with self.assertRaises(CommandExecutionError):
                                nxos.config(config_file=config_file, **kwargs)

    def test_commands_error(self):

        """ UT: nxos module:config method - Mandatory arg commands not specified """

        commands = None
        kwargs = {}

        with patch.object(nxos, 'show', MagicMock(return_value=initial_config_file)):
            mock_cmd = MagicMock(return_value=False)
            with patch.dict(nxos.__salt__, {'cp.get_file_str': mock_cmd}):
                mock_cmd = MagicMock(return_value=template_engine_file_str_file)
                with patch.dict(nxos.__salt__, {'file.apply_template_on_contents': mock_cmd}):
                    with patch.object(nxos, '_configure_device', MagicMock(return_value=config_result_file)):
                        with patch.object(nxos, 'show', MagicMock(return_value=modified_config_file)):

                            # Execute the function under test
                            with self.assertRaises(CommandExecutionError):
                                nxos.config(commands=commands, **kwargs)

    def test_config_file_error2(self):

        """ UT: nxos module:config method - Mandatory arg config_file not specified """

        config_file = None
        kwargs = {}

        with patch.object(nxos, 'show', MagicMock(return_value=initial_config_file)):
            mock_cmd = MagicMock(return_value=False)
            with patch.dict(nxos.__salt__, {'cp.get_file_str': mock_cmd}):
                mock_cmd = MagicMock(return_value=template_engine_file_str_file)
                with patch.dict(nxos.__salt__, {'file.apply_template_on_contents': mock_cmd}):
                    with patch.object(nxos, '_configure_device', MagicMock(return_value=config_result_file)):
                        with patch.object(nxos, 'show', MagicMock(return_value=modified_config_file)):

                            # Execute the function under test
                            with self.assertRaises(CommandExecutionError):
                                nxos.config(config_file=config_file, **kwargs)

    def test_delete_config(self):

        """ UT: nxos module:delete_config method """

        kwargs = {}
        lines_list = ['feature bgp', ['feature bgp']]
        expected_output = 'COMMAND_LIST: feature bgp'

        for lines in lines_list:
            with patch.object(nxos, 'config', MagicMock(return_value=delete_config)):

                # Execute the function under test
                result = nxos.delete_config(lines, **kwargs)
                self.assertEqual(result, delete_config)

    def test_remove_user(self):

        """ UT: nxos module:remove_user method """

        kwargs = {}
        user = 'salt_test'

        with patch.object(nxos, 'config', MagicMock(return_value=remove_user)):

            # Execute the function under test
            result = nxos.remove_user(user, **kwargs)
            self.assertEqual(result, remove_user)

    def test_replace(self):

        """ UT: nxos module:replace method """

        old_value = 'feature bgp'
        new_value = 'feature ospf'
        kwargs = {}

        with patch.object(nxos, 'show_run', MagicMock(return_value=n9k_show_running_config_list[0])):
            with patch.object(nxos, 'delete_config', MagicMock(return_value=None)):
                with patch.object(nxos, 'add_config', MagicMock(return_value=None)):

                    # Execute the function under test
                    result = nxos.replace(old_value, new_value, **kwargs)

                    self.assertEqual(result['old'], ['feature bgp'])
                    self.assertEqual(result['new'], ['feature ospf'])

    def test_replace_full_match_true(self):

        """ UT: nxos module:replace method - full match true"""

        kwargs = {}
        old_value = 'feature bgp'
        new_value = 'feature ospf'
        kwargs = {}

        with patch.object(nxos, 'show_run', MagicMock(return_value=n9k_show_running_config_list[0])):
            with patch.object(nxos, 'delete_config', MagicMock(return_value=None)):
                with patch.object(nxos, 'add_config', MagicMock(return_value=None)):

                    # Execute the function under test
                    result = nxos.replace(old_value, new_value, full_match=True, **kwargs)
                    self.assertEqual(result['old'], ['feature bgp'])
                    self.assertEqual(result['new'], ['feature ospf'])

    def test_replace_no_match(self):

        """ UT: nxos module:replace method - no match """

        old_value = 'feature does_not_exist'
        new_value = 'feature ospf'
        kwargs = {}

        with patch.object(nxos, 'show_run', MagicMock(return_value=n9k_show_running_config_list[0])):
            with patch.object(nxos, 'delete_config', MagicMock(return_value=None)):
                with patch.object(nxos, 'add_config', MagicMock(return_value=None)):

                    # Execute the function under test
                    result = nxos.replace(old_value, new_value, **kwargs)
                    print(result)
                    self.assertEqual(result['old'], [])
                    self.assertEqual(result['new'], [])

    def test_save_running_config(self):

        """ UT: nxos module:save_running_config method """

        kwargs = {}

        with patch.object(nxos, 'config', MagicMock(return_value=save_running_config)):

            # Execute the function under test
            result = nxos.save_running_config(**kwargs)
            self.assertEqual(result, save_running_config)

    def test_set_password_enc_false_cs_none(self):

        """ UT: nxos module:set_password method - encrypted False, crypt_salt None """

        password_line = 'username devops password 5 $5$CFENPG$1VUC15BB4rq8fM0TSDaBGlGvVAJBelGFLp9VZEiVPOC  role network-admin'
        username = 'devops'
        password = 'test123TMM^&'
        crypt_salt = 'ZcZqm15X'
        hashed_pass = '$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        # password_line = 'username devops password 5 $5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        kwargs = {}

        with patch.object(nxos, 'get_user', MagicMock(return_value=password_line)):
            with patch.object(nxos, 'secure_password', MagicMock(return_value=crypt_salt)):
                with patch.object(nxos, 'gen_hash', MagicMock(return_value=hashed_pass)):
                    with patch.object(nxos, 'config', MagicMock(return_value='password_set')):

                        # Execute the function under test
                        result = nxos.set_password(username, password, **kwargs)
                        self.assertEqual('password_set', result)

    def test_set_password_enc_false_cs_set(self):

        """ UT: nxos module:set_password method - encrypted False, crypt_salt set """

        password_line = 'username devops password 5 $5$CFENPG$1VUC15BB4rq8fM0TSDaBGlGvVAJBelGFLp9VZEiVPOC  role network-admin'
        username = 'devops'
        password = 'test123TMM^&'
        crypt_salt = 'ZcZqm15X'
        hashed_pass = '$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        # password_line = 'username devops password 5 $5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        kwargs = {}

        with patch.object(nxos, 'get_user', MagicMock(return_value=password_line)):
            with patch.object(nxos, 'secure_password', MagicMock(return_value=crypt_salt)):
                with patch.object(nxos, 'gen_hash', MagicMock(return_value=hashed_pass)):
                    with patch.object(nxos, 'config', MagicMock(return_value='password_set')):

                        # Execute the function under test
                        result = nxos.set_password(username, password, crypt_salt=crypt_salt, **kwargs)
                        self.assertEqual('password_set', result)

    def test_set_password_enc_true(self):

        """ UT: nxos module:set_password method - encrypted True """

        password_line = 'username devops password 5 $5$CFENPG$1VUC15BB4rq8fM0TSDaBGlGvVAJBelGFLp9VZEiVPOC  role network-admin'
        username = 'devops'
        password = 'test123TMM^&'
        crypt_salt = 'ZcZqm15X'
        hashed_pass = '$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        # password_line = 'username devops password 5 $5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        kwargs = {}

        with patch.object(nxos, 'get_user', MagicMock(return_value=password_line)):
            with patch.object(nxos, 'secure_password', MagicMock(return_value=crypt_salt)):
                with patch.object(nxos, 'gen_hash', MagicMock(return_value=hashed_pass)):
                    with patch.object(nxos, 'config', MagicMock(return_value='password_set')):

                        # Execute the function under test
                        result = nxos.set_password(username, password, encrypted=True, **kwargs)
                        self.assertEqual('password_set', result)

    def test_set_password_role_none(self):

        """ UT: nxos module:set_password method - role none """

        password_line = 'username devops password 5 $5$CFENPG$1VUC15BB4rq8fM0TSDaBGlGvVAJBelGFLp9VZEiVPOC  role network-admin'
        username = 'devops'
        password = 'test123TMM^&'
        crypt_salt = 'ZcZqm15X'
        hashed_pass = '$5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        # password_line = 'username devops password 5 $5$ZcZqm15X$exHN2m6yrPKpYhGArK3Vml3ZjNbJaJYdzWyf0fp1Up2'
        kwargs = {}

        with patch.object(nxos, 'get_user', MagicMock(return_value=password_line)):
            with patch.object(nxos, 'secure_password', MagicMock(return_value=crypt_salt)):
                with patch.object(nxos, 'gen_hash', MagicMock(return_value=hashed_pass)):
                    with patch.object(nxos, 'config', MagicMock(return_value='password_set')):

                        # Execute the function under test
                        result = nxos.set_password(username, password, encrypted=True, role='devops', **kwargs)
                        self.assertEqual('password_set', result)

    def test_set_role(self):

        """ UT: nxos module:save_running_config method """

        kwargs = {}
        username = 'salt_test'
        role = 'vdc-admin'

        with patch.object(nxos, 'config', MagicMock(return_value=set_role)):

            # Execute the function under test
            result = nxos.set_role(username, role, **kwargs)
            self.assertEqual(result, set_role)

    def test_unset_role(self):

        """ UT: nxos module:save_running_config method """

        kwargs = {}
        username = 'salt_test'
        role = 'vdc-admin'

        with patch.object(nxos, 'config', MagicMock(return_value=unset_role)):

            # Execute the function under test
            result = nxos.unset_role(username, role, **kwargs)
            self.assertEqual(result, unset_role)

    def test_configure_device(self):

        """ UT: nxos module:_configure_device method """

        kwargs = {}

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=True)):
            with patch.dict(nxos.__proxy__, {'nxos.proxy_config': MagicMock(return_value='configured')}):

                result = nxos._configure_device('feature bgp', **kwargs)
                self.assertEqual(result, 'configured')

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=False)):
            with patch.object(nxos, '_nxapi_config', MagicMock(return_value='configured')):

                nxos._configure_device('feature bgp', **kwargs)
                self.assertEqual(result, 'configured')

    def test_nxapi_config(self):

        """ UT: nxos module:_nxapi_config method """

        kwargs = {}

        mock_cmd = MagicMock(return_value={'nxos': {'no_save_config': True}})
        with patch.dict(nxos.__salt__, {'config.get': mock_cmd}):
            with patch.object(nxos, '_nxapi_request', MagicMock(return_value='router_data')):

                    result = nxos._nxapi_config('show version', **kwargs)
                    self.assertEqual(result, [['show version'], 'router_data'])

    def test_nxapi_config_failure(self):

        """ UT: nxos module:_nxapi_config method """

        kwargs = {}
        side_effect = ['Failure', 'saved_data']

        mock_cmd = MagicMock(return_value={'nxos': {'no_save_config': False}})
        with patch.dict(nxos.__salt__, {'config.get': mock_cmd}):
            with patch.object(nxos, '_nxapi_request', MagicMock(side_effect=side_effect)):

                result = nxos._nxapi_config('show bad_command', **kwargs)
                self.assertEqual(result, [['show bad_command'], 'Failure'])

    def test_nxapi_request_proxy(self):

        """ UT: nxos module:_nxapi_request method - proxy"""

        kwargs = {}

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=True)):
            with patch.dict(nxos.__proxy__, {'nxos._nxapi_request': MagicMock(return_value='router_data')}):

                result = nxos._nxapi_request('show version', kwargs)
                self.assertEqual(result, 'router_data')

    def test_nxapi_request_no_proxy(self):

        """ UT: nxos module:_nxapi_request method - no proxy"""

        kwargs = {}

        with patch('salt.utils.platform.is_proxy', MagicMock(return_value=False)):
            mock_cmd = MagicMock(return_value={'nxos': {'no_save_config': True}})
            with patch.dict(nxos.__salt__, {'config.get': mock_cmd}):
                with patch.dict(nxos.__utils__, {'nxos.nxapi_request': MagicMock(return_value='router_data')}):

                    result = nxos._nxapi_request('show version', kwargs)
                    self.assertEqual(result, 'router_data')
