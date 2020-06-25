# -*- coding: utf-8 -*-

"""
    :codeauthor: Mike Wiebe <@mikewiebe>
"""

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

import salt.states.nxos as nxos_state

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NxosNxapiStatesTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {nxos_state: {}}

    def test_user_present_create(self):

        """ UT: nxos module:user_present method - create """

        roles = ["vdc-admin"]

        side_effect = MagicMock(side_effect=[[], "", "set_role", roles, roles])
        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_present("daniel", roles=roles)

                self.assertEqual(result["name"], "daniel")
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"]["roles"]["new"], ["vdc-admin"])
                self.assertEqual(result["changes"]["roles"]["old"], [])
                self.assertEqual(result["comment"], "User set correctly")

    def test_user_present_create_opts_test(self):

        """ UT: nxos module:user_present method - create """

        roles = ["vdc-admin"]

        side_effect = MagicMock(side_effect=[[], "", "set_role", roles, roles])
        with patch.dict(nxos_state.__opts__, {"test": True}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_present("daniel", roles=roles)

                self.assertEqual(result["name"], "daniel")
                self.assertEqual(result["result"], None)
                self.assertEqual(result["changes"]["role"]["add"], ["vdc-admin"])
                self.assertEqual(result["changes"]["role"]["remove"], [])
                self.assertEqual(result["comment"], "User will be created")

    def test_user_present_create_non_defaults(self):

        """ UT: nxos module:user_present method - create non default opts """

        username = "daniel"
        password = "ghI&435y55#"
        roles = ["vdc-admin", "dev-ops"]
        encrypted = False
        crypt_salt = "foobar123"
        algorithm = "md5"

        # [change_password, cur_roles, old_user, new_user, set_role, set_role,
        # get_roles, correct_password, cur_roles]
        side_effect = MagicMock(
            side_effect=[
                False,
                [],
                "",
                "new_user",
                "set_role",
                "set_role",
                roles,
                True,
                roles,
            ]
        )
        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):
                result = nxos_state.user_present(
                    username,
                    password=password,
                    roles=roles,
                    encrypted=encrypted,
                    crypt_salt=crypt_salt,
                    algorithm=algorithm,
                )

                self.assertEqual(result["name"], "daniel")
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"]["password"]["new"], "new_user")
                self.assertEqual(result["changes"]["password"]["old"], "")
                self.assertEqual(
                    result["changes"]["roles"]["new"], ["vdc-admin", "dev-ops"]
                )
                self.assertEqual(result["changes"]["roles"]["old"], [])
                self.assertEqual(result["comment"], "User set correctly")

    def test_user_present_create_encrypted_password_no_roles_opts_test(self):

        """ UT: nxos module:user_present method - encrypted password, no roles """

        username = "daniel"
        password = "$1$foobar12$K7x4Rxua11qakvrRjcwDC/"
        encrypted = True
        crypt_salt = "foobar123"
        algorithm = "md5"

        side_effect = MagicMock(side_effect=[False, "", "new_user", True])

        with patch.dict(nxos_state.__opts__, {"test": True}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_present(
                    username,
                    password=password,
                    encrypted=encrypted,
                    crypt_salt=crypt_salt,
                    algorithm=algorithm,
                )

                self.assertEqual(result["name"], "daniel")
                self.assertEqual(result["result"], None)
                self.assertEqual(result["changes"]["password"], True)
                self.assertEqual(result["comment"], "User will be created")

    def test_user_present_create_user_exists(self):

        """ UT: nxos module:user_present method - user exists """

        username = "daniel"
        password = "$1$foobar12$K7x4Rxua11qakvrRjcwDC/"
        encrypted = True
        crypt_salt = "foobar123"
        algorithm = "md5"

        side_effect = MagicMock(side_effect=[True, "user_exists"])

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_present(
                    username,
                    password=password,
                    encrypted=encrypted,
                    crypt_salt=crypt_salt,
                    algorithm=algorithm,
                )

                self.assertEqual(result["name"], "daniel")
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"], {})
                self.assertEqual(result["comment"], "User already exists")

    def test_user_present_create_user_exists_opts_test(self):

        """ UT: nxos module:user_present method - user exists """

        username = "daniel"
        password = "$1$foobar12$K7x4Rxua11qakvrRjcwDC/"
        roles = ["vdc-admin", "dev-opts"]
        new_roles = ["network-operator"]
        encrypted = True
        crypt_salt = "foobar123"
        algorithm = "md5"

        side_effect = MagicMock(side_effect=[True, roles, "user_exists"])

        with patch.dict(nxos_state.__opts__, {"test": True}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_present(
                    username,
                    password=password,
                    roles=new_roles,
                    encrypted=encrypted,
                    crypt_salt=crypt_salt,
                    algorithm=algorithm,
                )

                remove = result["changes"]["roles"]["remove"]
                remove.sort()
                self.assertEqual(result["name"], "daniel")
                self.assertEqual(result["result"], None)
                self.assertEqual(
                    result["changes"]["roles"]["add"], ["network-operator"]
                )
                self.assertEqual(remove, ["dev-opts", "vdc-admin"])
                self.assertEqual(result["comment"], "User will be updated")

    def test_user_absent(self):

        """ UT: nxos module:user_absent method - remove user """

        username = "daniel"

        side_effect = MagicMock(side_effect=["daniel", "remove_user", ""])

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_absent(username)

                self.assertEqual(result["name"], "daniel")
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"]["old"], "daniel")
                self.assertEqual(result["changes"]["new"], "")
                self.assertEqual(result["comment"], "User removed")

    def test_user_absent_user_does_not_exist(self):

        """ UT: nxos module:user_absent method - remove user """

        username = "daniel"

        side_effect = MagicMock(side_effect=[""])

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_absent(username)

                self.assertEqual(result["name"], "daniel")
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"], {})
                self.assertEqual(result["comment"], "User does not exist")

    def test_user_absent_test_opts(self):

        """ UT: nxos module:user_absent method - remove user """

        username = "daniel"

        side_effect = MagicMock(side_effect=["daniel", "remove_user", ""])

        with patch.dict(nxos_state.__opts__, {"test": True}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.user_absent(username)

                self.assertEqual(result["name"], "daniel")
                self.assertEqual(result["result"], None)
                self.assertEqual(result["changes"]["old"], "daniel")
                self.assertEqual(result["changes"]["new"], "")
                self.assertEqual(result["comment"], "User will be removed")

    def test_config_present(self):

        """ UT: nxos module:config_present method - add config """

        config_data = [
            "snmp-server community randomSNMPstringHERE group network-operator",
            "snmp-server community AnotherRandomSNMPSTring group network-admin",
        ]
        snmp_matches1 = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]
        snmp_matches2 = [
            ["snmp-server community AnotherRandomSNMPSTring group network-admin"]
        ]

        side_effect = MagicMock(
            side_effect=[
                [],
                "add_snmp_config1",
                snmp_matches1,
                "add_snmp_config2",
                snmp_matches2,
            ]
        )

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.config_present(config_data)

                self.assertEqual(result["name"], config_data)
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"]["new"], config_data)
                self.assertEqual(result["comment"], "Successfully added config")

    def test_config_present_already_configured(self):

        """ UT: nxos module:config_present method - add config already configured """

        config_data = [
            "snmp-server community randomSNMPstringHERE group network-operator",
            "snmp-server community AnotherRandomSNMPSTring group network-admin",
        ]

        side_effect = MagicMock(side_effect=[config_data[0], config_data[1]])

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.config_present(config_data)

                self.assertEqual(result["name"], config_data)
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"], {})
                self.assertEqual(result["comment"], "Config is already set")

    def test_config_present_test_opts(self):

        """ UT: nxos module:config_present method - add config """

        config_data = [
            "snmp-server community randomSNMPstringHERE group network-operator",
            "snmp-server community AnotherRandomSNMPSTring group network-admin",
        ]
        snmp_matches1 = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]
        snmp_matches2 = [
            ["snmp-server community AnotherRandomSNMPSTring group network-admin"]
        ]

        side_effect = MagicMock(
            side_effect=[
                [],
                "add_snmp_config1",
                snmp_matches1,
                "add_snmp_config2",
                snmp_matches2,
            ]
        )

        with patch.dict(nxos_state.__opts__, {"test": True}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.config_present(config_data)

                self.assertEqual(result["name"], config_data)
                self.assertEqual(result["result"], None)
                self.assertEqual(result["changes"]["new"], config_data)
                self.assertEqual(result["comment"], "Config will be added")

    def test_config_present_fail_to_add(self):

        """ UT: nxos module:config_present method - add config fails"""

        config_data = [
            "snmp-server community randomSNMPstringHERE group network-operator",
            "snmp-server community AnotherRandomSNMPSTring group network-admin",
        ]
        snmp_matches1 = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]
        snmp_matches2 = [
            ["snmp-server community AnotherRandomSNMPSTring group network-admin"]
        ]

        side_effect = MagicMock(
            side_effect=[[], "add_snmp_config1", "", "add_snmp_config2", ""]
        )

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.config_present(config_data)

                self.assertEqual(result["name"], config_data)
                self.assertFalse(result["result"])
                self.assertEqual(result["changes"], {})
                self.assertEqual(result["comment"], "Failed to add config")

    def test_replace(self):

        """ UT: nxos module:replace method - replace config """

        name = "randomSNMPstringHERE"
        repl = "NEWrandoSNMPstringHERE"
        matches_before = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]
        match_after = []
        changes = {}
        changes["new"] = [
            "snmp-server community NEWrandoSNMPstringHERE group network-operator"
        ]
        changes["old"] = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]

        side_effect = MagicMock(side_effect=[matches_before, changes, match_after])

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.replace(name, repl)

                self.assertEqual(result["name"], name)
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"]["new"], changes["new"])
                self.assertEqual(result["changes"]["old"], changes["old"])
                self.assertEqual(
                    result["comment"],
                    'Successfully replaced all instances of "randomSNMPstringHERE" with "NEWrandoSNMPstringHERE"',
                )

    def test_replace_test_opts(self):

        """ UT: nxos module:replace method - replace config """

        name = "randomSNMPstringHERE"
        repl = "NEWrandoSNMPstringHERE"
        matches_before = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]
        match_after = []
        changes = {}
        changes["new"] = [
            "snmp-server community NEWrandoSNMPstringHERE group network-operator"
        ]
        changes["old"] = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]

        side_effect = MagicMock(side_effect=[matches_before, changes, match_after])

        with patch.dict(nxos_state.__opts__, {"test": True}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.replace(name, repl)

                self.assertEqual(result["name"], name)
                self.assertEqual(result["result"], None)
                self.assertEqual(result["changes"]["new"], changes["new"])
                self.assertEqual(result["changes"]["old"], changes["old"])
                self.assertEqual(result["comment"], "Configs will be changed")

    def test_config_absent(self):

        """ UT: nxos module:config_absent method - remove config """

        config_data = [
            "snmp-server community randomSNMPstringHERE group network-operator",
            "snmp-server community AnotherRandomSNMPSTring group network-admin",
        ]
        snmp_matches1 = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]
        snmp_matches2 = [
            ["snmp-server community AnotherRandomSNMPSTring group network-admin"]
        ]

        side_effect = MagicMock(
            side_effect=[
                snmp_matches1,
                "remove_config",
                [],
                snmp_matches2,
                "remove_config",
                [],
            ]
        )

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.config_absent(config_data)

                self.assertEqual(result["name"], config_data)
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"]["new"], config_data)
                self.assertEqual(result["comment"], "Successfully deleted config")

    def test_config_absent_already_configured(self):

        """ UT: nxos module:config_absent method - add config removed """

        config_data = [
            "snmp-server community randomSNMPstringHERE group network-operator",
            "snmp-server community AnotherRandomSNMPSTring group network-admin",
        ]

        side_effect = MagicMock(side_effect=[[], []])

        with patch.dict(nxos_state.__opts__, {"test": False}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.config_absent(config_data)

                self.assertEqual(result["name"], config_data)
                self.assertTrue(result["result"])
                self.assertEqual(result["changes"], {})
                self.assertEqual(result["comment"], "Config is already absent")

    def test_config_absent_test_opts(self):

        """ UT: nxos module:config_absent method - remove config """

        config_data = [
            "snmp-server community randomSNMPstringHERE group network-operator",
            "snmp-server community AnotherRandomSNMPSTring group network-admin",
        ]
        snmp_matches1 = [
            "snmp-server community randomSNMPstringHERE group network-operator"
        ]
        snmp_matches2 = [
            ["snmp-server community AnotherRandomSNMPSTring group network-admin"]
        ]

        side_effect = MagicMock(
            side_effect=[
                snmp_matches1,
                "remove_config",
                [],
                snmp_matches2,
                "remove_config",
                [],
            ]
        )

        with patch.dict(nxos_state.__opts__, {"test": True}):
            with patch.dict(nxos_state.__salt__, {"nxos.cmd": side_effect}):

                result = nxos_state.config_absent(config_data)

                self.assertEqual(result["name"], config_data)
                self.assertEqual(result["result"], None)
                self.assertEqual(result["changes"]["new"], config_data)
                self.assertEqual(result["comment"], "Config will be removed")
