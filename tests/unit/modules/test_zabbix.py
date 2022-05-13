"""
    :codeauthor: :email:`Christian McHugh <christian.mchugh@gmail.com>`
"""

import salt.modules.config as config
import salt.modules.zabbix as zabbix
from salt.exceptions import SaltException
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

CONN_ARGS = {}
CONN_ARGS["url"] = "http://test.url"
CONN_ARGS["auth"] = "1234"

GETID_QUERY_RESULT_OK = [
    {"internal": "0", "flags": "0", "groupid": "11", "name": "Databases"}
]
GETID_QUERY_RESULT_BAD = [
    {"internal": "0", "flags": "0", "groupid": "11", "name": "Databases"},
    {"another": "object"},
]

DEFINED_PARAMS = {
    "name": "beta",
    "eventsource": 2,
    "status": 0,
    "filter": {
        "evaltype": 2,
        "conditions": [{"conditiontype": 24, "operator": 2, "value": "db"}],
    },
    "operations": [
        {"operationtype": 2},
        {
            "operationtype": 4,
            "opgroup": [
                {"groupid": {"query_object": "hostgroup", "query_name": "Databases"}}
            ],
        },
    ],
    "empty_list": [],
}

SUBSTITUTED_DEFINED_PARAMS = {
    "status": "0",
    "filter": {
        "evaltype": "2",
        "conditions": [{"operator": "2", "conditiontype": "24", "value": "db"}],
    },
    "eventsource": "2",
    "name": "beta",
    "operations": [
        {"operationtype": "2"},
        {"opgroup": [{"groupid": "11"}], "operationtype": "4"},
    ],
    "empty_list": [],
}

EXISTING_OBJECT_PARAMS = {
    "status": "0",
    "operations": [
        {
            "operationtype": "2",
            "esc_period": "0",
            "evaltype": "0",
            "opconditions": [],
            "esc_step_to": "1",
            "actionid": "23",
            "esc_step_from": "1",
            "operationid": "64",
        },
        {
            "operationtype": "4",
            "esc_period": "0",
            "evaltype": "0",
            "opconditions": [],
            "esc_step_to": "1",
            "actionid": "23",
            "esc_step_from": "1",
            "opgroup": [{"groupid": "11", "operationid": "65"}],
            "operationid": "65",
        },
    ],
    "def_shortdata": "",
    "name": "beta",
    "esc_period": "0",
    "def_longdata": "",
    "filter": {
        "formula": "",
        "evaltype": "2",
        "conditions": [
            {
                "operator": "2",
                "conditiontype": "24",
                "formulaid": "A",
                "value": "DIFFERENT VALUE HERE",
            }
        ],
        "eval_formula": "A",
    },
    "eventsource": "2",
    "actionid": "23",
    "r_shortdata": "",
    "r_longdata": "",
    "recovery_msg": "0",
    "empty_list": [{"dict_key": "dic_val"}],
}

DIFF_PARAMS_RESULT = {
    "filter": {
        "evaltype": "2",
        "conditions": [{"operator": "2", "conditiontype": "24", "value": "db"}],
    },
    "empty_list": [],
}

DIFF_PARAMS_RESULT_WITH_ROLLBACK = {
    "new": DIFF_PARAMS_RESULT,
    "old": {
        "filter": {
            "formula": "",
            "evaltype": "2",
            "conditions": [
                {
                    "operator": "2",
                    "conditiontype": "24",
                    "formulaid": "A",
                    "value": "DIFFERENT VALUE HERE",
                }
            ],
            "eval_formula": "A",
        },
        "empty_list": [{"dict_key": "dic_val"}],
    },
}


class ZabbixTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.zabbix
    """

    def setup_loader_modules(self):
        return {
            zabbix: {
                "__salt__": {
                    "cmd.which_bin": lambda _: "zabbix_server",
                    "config.get": config.get,
                }
            },
            config: {"__opts__": {}},
        }

    def test_get_object_id_by_params(self):
        """
        Test get_object_id function with expected result from API call
        """
        with patch(
            "salt.modules.zabbix.run_query",
            MagicMock(return_value=GETID_QUERY_RESULT_OK),
        ):
            self.assertEqual(
                zabbix.get_object_id_by_params("hostgroup", "Databases"), "11"
            )

    def test_get_obj_id_by_params_fail(self):
        """
        Test get_object_id function with unexpected result from API call
        """
        with patch(
            "salt.modules.zabbix.run_query",
            MagicMock(return_value=GETID_QUERY_RESULT_BAD),
        ):
            self.assertRaises(
                SaltException, zabbix.get_object_id_by_params, "hostgroup", "Databases"
            )

    def test_substitute_params(self):
        """
        Test proper parameter substitution for defined input
        """
        with patch(
            "salt.modules.zabbix.get_object_id_by_params", MagicMock(return_value="11")
        ):
            self.assertEqual(
                zabbix.substitute_params(DEFINED_PARAMS), SUBSTITUTED_DEFINED_PARAMS
            )

    def test_substitute_params_fail(self):
        """
        Test proper parameter substitution if there is needed parameter missing
        """
        self.assertRaises(
            SaltException,
            zabbix.substitute_params,
            {"groupid": {"query_object": "hostgroup"}},
        )

    def test_compare_params(self):
        """
        Test result comparison of two params structures
        """
        self.assertEqual(
            zabbix.compare_params(SUBSTITUTED_DEFINED_PARAMS, EXISTING_OBJECT_PARAMS),
            DIFF_PARAMS_RESULT,
        )

    def test_compare_params_rollback(self):
        """
        Test result comparison of two params structures with rollback return value option
        """
        self.assertEqual(
            zabbix.compare_params(
                SUBSTITUTED_DEFINED_PARAMS, EXISTING_OBJECT_PARAMS, True
            ),
            DIFF_PARAMS_RESULT_WITH_ROLLBACK,
        )

    def test_compare_params_fail(self):
        """
        Test result comparison of two params structures where some data type mismatch exists
        """
        self.assertRaises(
            SaltException, zabbix.compare_params, {"dict": "val"}, {"dict": ["list"]}
        )

    def test_apiinfo_version(self):
        """
        Test apiinfo_version
        """
        module_return = "3.4.5"
        query_return = {"jsonrpc": "2.0", "result": "3.4.5", "id": 1}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(zabbix.apiinfo_version(**CONN_ARGS), module_return)

    def test__login_getting_nested_parameters_from_config(self):
        """
        Test get the connection data as nested parameters from config
        """
        query_return = {"jsonrpc": "2.0", "result": "3.4.5", "id": 1}
        fake_connection_data = {
            "zabbix": {
                "user": "testuser",
                "password": "password",
                "url": "http://fake_url/zabbix/api_jsonrpc.php",
            }
        }
        login_return = {
            "url": "http://fake_url/zabbix/api_jsonrpc.php",
            "auth": "3.4.5",
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.dict(zabbix.__pillar__, fake_connection_data):
                self.assertEqual(zabbix._login(), login_return)

    def test__login_getting_flat_parameters_from_config(self):
        """
        Test get the connection data as flat parameters from config
        """
        query_return = {"jsonrpc": "2.0", "result": "3.4.5", "id": 1}
        fake_connection_data = {
            "zabbix.user": "testuser",
            "zabbix.password": "password",
            "zabbix.url": "http://fake_url/zabbix/api_jsonrpc.php",
        }
        login_return = {
            "url": "http://fake_url/zabbix/api_jsonrpc.php",
            "auth": "3.4.5",
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.dict(zabbix.__pillar__, fake_connection_data):
                self.assertEqual(zabbix._login(), login_return)

    def test__login_getting_empty_parameters_from_config(self):
        """
        Test get the connection data from config with an empty response
        """
        query_return = {"jsonrpc": "2.0", "result": "3.4.5", "id": 1}
        fake_connection_data = {}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.dict(zabbix.__pillar__, fake_connection_data):
                with self.assertRaises(SaltException) as login_exception:
                    ret = zabbix._login()
                    self.assertEqual(
                        login_exception.strerror,
                        "URL is probably not correct! ('user')",
                    )

    def test_get_mediatype(self):
        """
        query_submitted = { "params": {"filter": {"description": 10}, "output": "extend"},
        "id": 0, "auth": "251feb98e3c25b6b7fb984b6c7a79817", "method": "mediatype.get"}
        """

        module_return = [
            {
                "mediatypeid": "10",
                "type": "0",
                "name": "Testing",
                "smtp_server": "mail.example.com",
                "smtp_helo": "example.com",
                "smtp_email": "zabbix@example.com",
            }
        ]

        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "mediatypeid": "10",
                    "type": "0",
                    "name": "Testing",
                    "smtp_server": "mail.example.com",
                    "smtp_helo": "example.com",
                    "smtp_email": "zabbix@example.com",
                }
            ],
            "id": 0,
        }
        zabbix_version_return_list = ["3.4", "4.4.5"]
        for zabbix_version_return in zabbix_version_return_list:
            patch_apiinfo_version = patch.object(
                zabbix,
                "apiinfo_version",
                autospec=True,
                return_value=zabbix_version_return,
            )
            patch_query = patch.object(
                zabbix, "_query", autospec=True, return_value=query_return
            )
            patch_login = patch.object(
                zabbix, "_login", autospec=True, return_value=CONN_ARGS
            )
            with patch_apiinfo_version, patch_query, patch_login:
                self.assertEqual(zabbix.mediatype_get("10", **CONN_ARGS), module_return)

    def test_user_create(self):
        """
        query_submitted = {"params": {"passwd": "password007", "alias": "james",
        "name": "James Bond", "usrgrps": [{"usrgrpid": 7}, {"usrgrpid": 12}]},
        "jsonrpc": "2.0", "id": 0, "auth": "f016981c4f0d3f8b9682e34588fe8a33",
        "method": "user.create"}
        """

        module_return = ["3"]
        query_return = {"jsonrpc": "2.0", "result": {"userids": ["3"]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.user_create(
                        "james",
                        "password007",
                        "[7, 12]",
                        firstname="James Bond",
                        **CONN_ARGS
                    ),
                    module_return,
                )

    def test_user_delete(self):
        """
        query_submitted = {"params": [3], "jsonrpc": "2.0", "id": 0,
        "auth": "68d38eace8e42a35c8d0c6a2ab0245a6", "method": "user.delete"}
        """

        module_return = ["3"]
        query_return = {"jsonrpc": "2.0", "result": {"userids": ["3"]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(zabbix.user_delete(3, **CONN_ARGS), module_return)

    def test_user_exists(self):
        """
        query_submitted = {"params": {"filter": {"alias": "Admin"}, "output": "extend"},
        "jsonrpc": "2.0", "id": 0, "auth": "72435c7f754cb2adb4ecddc98216057f",
        "method": "user.get"}
        """

        module_return = True
        # pylint: disable=E8128
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "userid": "1",
                    "alias": "Admin",
                    "name": "Zabbix",
                    "surname": "Administrator",
                    "url": "",
                    "autologin": "1",
                    "autologout": "0",
                    "lang": "en_GB",
                    "refresh": "30s",
                    "type": "3",
                    "theme": "default",
                    "attempt_failed": "0",
                    "attempt_ip": "10.0.2.2",
                    "attempt_clock": "1515922072",
                    "rows_per_page": "50",
                }
            ],
            "id": 0,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.user_exists("Admin", **CONN_ARGS), module_return
                )

    def test_user_get(self):
        """
        query_submitted = {"params": {"filter": {"alias": "Admin"}, "output": "extend"},
        "jsonrpc": "2.0", "id": 0, "auth": "49ef327f205d9e9150d4651cb6adc2d5",
        "method": "user.get"}
        """

        module_return = [
            {
                "lang": "en_GB",
                "rows_per_page": "50",
                "surname": "Administrator",
                "name": "Zabbix",
                "url": "",
                "attempt_clock": "1515922072",
                "userid": "1",
                "autologin": "1",
                "refresh": "30s",
                "attempt_failed": "0",
                "alias": "Admin",
                "theme": "default",
                "autologout": "0",
                "attempt_ip": "10.0.2.2",
                "type": "3",
            }
        ]
        # pylint: disable=E8128
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "userid": "1",
                    "alias": "Admin",
                    "name": "Zabbix",
                    "surname": "Administrator",
                    "url": "",
                    "autologin": "1",
                    "autologout": "0",
                    "lang": "en_GB",
                    "refresh": "30s",
                    "type": "3",
                    "theme": "default",
                    "attempt_failed": "0",
                    "attempt_ip": "10.0.2.2",
                    "attempt_clock": "1515922072",
                    "rows_per_page": "50",
                }
            ],
            "id": 0,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(zabbix.user_get("Admin", **CONN_ARGS), module_return)
                self.assertEqual(
                    zabbix.user_get(userids="1", **CONN_ARGS), module_return
                )

    def test_user_update(self):
        """
        query_submitted = {"params": {"userid": 3, "name": "James Brown"}, "jsonrpc": "2.0",
        "id": 0, "auth": "cdf2ee35e3bc47560585e9c457cbc398", "method": "user.update"}
        """

        module_return = ["3"]
        query_return = {"jsonrpc": "2.0", "result": {"userids": ["3"]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.user_update("3", visible_name="James Brown", **CONN_ARGS),
                    module_return,
                )

    def test_user_getmedia(self):
        """
        query_submitted = {"params": {"userids": 3}, "jsonrpc": "2.0", "id": 0,
        "auth": "d4de741ea7cdd434b3ba7b56efa4efaf", "method": "usermedia.get"}
        """

        module_return = [
            {
                "mediatypeid": "1",
                "mediaid": "1",
                "severity": "63",
                "userid": "3",
                "period": "1-7,00:00-24:00",
                "sendto": "email@example.com",
                "active": "0",
            }
        ]
        # pylint: disable=E8128
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "mediaid": "1",
                    "userid": "3",
                    "mediatypeid": "1",
                    "sendto": "email@example.com",
                    "active": "0",
                    "severity": "63",
                    "period": "1-7,00:00-24:00",
                }
            ],
            "id": 0,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(zabbix.user_getmedia("3", **CONN_ARGS), module_return)

    def test_user_addmedia(self):
        """
        query_submitted = {"params": {"medias": [{"active": 0, "mediatypeid": 1,
        "period": "1-7,00:00-24:00", "severity": 63, "sendto": "support2@example.com"}],
        "users": [{"userid": 1}]}, "jsonrpc": "2.0", "id": 0, "auth": "b347fc1bf1f5617b93755619a037c19e",
        "method": "user.addmedia"}
        """

        module_return = ["2"]
        query_return = {"jsonrpc": "2.0", "result": {"mediaids": ["2"]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.user_addmedia(
                        "1",
                        active="0",
                        mediatypeid="1",
                        period="1-7,00:00-24:00",
                        sendto="support2@example.com",
                        severity="63",
                        **CONN_ARGS
                    ),
                    module_return,
                )

    def test_user_deletemedia(self):
        """
        query_submitted = {"params": [1], "jsonrpc": "2.0", "id": 0, "auth": "9fb226c759a320de0de3b7a141404506",
        "method": "user.deletemedia"}
        """

        module_return = [1]
        query_return = {"jsonrpc": "2.0", "result": {"mediaids": [1]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.user_deletemedia("1", **CONN_ARGS), module_return
                )

    def test_user_list(self):
        """
        query_submitted = {"params": {"output": "extend"}, "jsonrpc": "2.0", "id": 0,
        "auth": "54d67b63c37e690cf06972678f1e9720", "method": "user.get"}
        """

        module_return = [
            {
                "lang": "en_GB",
                "rows_per_page": "50",
                "surname": "Administrator",
                "name": "Zabbix",
                "url": "",
                "attempt_clock": "1515922072",
                "userid": "1",
                "autologin": "1",
                "refresh": "30s",
                "attempt_failed": "0",
                "alias": "Admin",
                "theme": "default",
                "autologout": "0",
                "attempt_ip": "10.0.2.2",
                "type": "3",
            },
            {
                "lang": "en_GB",
                "rows_per_page": "50",
                "surname": "",
                "name": "",
                "url": "",
                "attempt_clock": "0",
                "userid": "2",
                "autologin": "0",
                "refresh": "30s",
                "attempt_failed": "0",
                "alias": "guest",
                "theme": "default",
                "autologout": "15m",
                "attempt_ip": "",
                "type": "1",
            },
            {
                "lang": "en_GB",
                "rows_per_page": "50",
                "surname": "",
                "name": "James Brown",
                "url": "",
                "attempt_clock": "0",
                "userid": "5",
                "autologin": "0",
                "refresh": "30s",
                "attempt_failed": "0",
                "alias": "james",
                "theme": "default",
                "autologout": "15m",
                "attempt_ip": "",
                "type": "1",
            },
        ]
        # pylint: disable=E8128
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "userid": "1",
                    "alias": "Admin",
                    "name": "Zabbix",
                    "surname": "Administrator",
                    "url": "",
                    "autologin": "1",
                    "autologout": "0",
                    "lang": "en_GB",
                    "refresh": "30s",
                    "type": "3",
                    "theme": "default",
                    "attempt_failed": "0",
                    "attempt_ip": "10.0.2.2",
                    "attempt_clock": "1515922072",
                    "rows_per_page": "50",
                },
                {
                    "userid": "2",
                    "alias": "guest",
                    "name": "",
                    "surname": "",
                    "url": "",
                    "autologin": "0",
                    "autologout": "15m",
                    "lang": "en_GB",
                    "refresh": "30s",
                    "type": "1",
                    "theme": "default",
                    "attempt_failed": "0",
                    "attempt_ip": "",
                    "attempt_clock": "0",
                    "rows_per_page": "50",
                },
                {
                    "userid": "5",
                    "alias": "james",
                    "name": "James Brown",
                    "surname": "",
                    "url": "",
                    "autologin": "0",
                    "autologout": "15m",
                    "lang": "en_GB",
                    "refresh": "30s",
                    "type": "1",
                    "theme": "default",
                    "attempt_failed": "0",
                    "attempt_ip": "",
                    "attempt_clock": "0",
                    "rows_per_page": "50",
                },
            ],
            "id": 0,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(zabbix.user_list(**CONN_ARGS), module_return)

    def test_usergroup_create(self):
        """
        query_submitted = {"params": {"name": "testgroup"}, "jsonrpc": "2.0", "id": 0,
        "auth": "7f3ac5e90201e5de4eb19e5322606575", "method": "usergroup.create"}
        """

        module_return = ["13"]
        query_return = {"jsonrpc": "2.0", "result": {"usrgrpids": ["13"]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.usergroup_create("testgroup", **CONN_ARGS), module_return
                )

    def test_usergroup_delete(self):
        """
        query_submitted = {"params": [13], "jsonrpc": "2.0", "id": 0,
        "auth": "9bad39de2a5a9211da588dd06dad8773", "method": "usergroup.delete"}
        """

        module_return = ["13"]
        query_return = {"jsonrpc": "2.0", "result": {"usrgrpids": ["13"]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.usergroup_delete("13", **CONN_ARGS), module_return
                )

    def test_usergroup_exists(self):
        """
        query_submitted = {"params": {"filter": {"name": "testgroup"}, "output": "extend",
        "selectRights": "extend"}, "jsonrpc": "2.0", "id": 0, "auth": "e62424cd7aa71f6748e1d69c190ac852",
        "method": "usergroup.get"}
        """

        module_return = True
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "usrgrpid": "13",
                    "name": "testgroup",
                    "gui_access": "0",
                    "users_status": "0",
                    "debug_mode": "0",
                    "rights": [],
                }
            ],
            "id": 0,
        }

        with patch.object(zabbix, "apiinfo_version", return_value="3.2"):
            with patch.object(zabbix, "_query", return_value=query_return):
                with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                    self.assertEqual(
                        zabbix.usergroup_exists("testgroup", **CONN_ARGS), module_return
                    )

    def test_usergroup_get(self):
        """
        query_submitted = {"params": {"filter": {"name": "testgroup"}, "output": "extend",
        "selectRights": "extend"}, "jsonrpc": "2.0", "id": 0, "auth": "739cf358050f2a2d33162fdcfa714a3c",
        "method": "usergroup.get"}
        """

        module_return = [
            {
                "name": "testgroup",
                "rights": [],
                "users_status": "0",
                "gui_access": "0",
                "debug_mode": "0",
                "usrgrpid": "13",
            }
        ]
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "usrgrpid": "13",
                    "name": "testgroup",
                    "gui_access": "0",
                    "users_status": "0",
                    "debug_mode": "0",
                    "rights": [],
                }
            ],
            "id": 0,
        }

        with patch.object(zabbix, "apiinfo_version", return_value="3.2"):
            with patch.object(zabbix, "_query", return_value=query_return):
                with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                    self.assertEqual(
                        zabbix.usergroup_get("testgroup", **CONN_ARGS), module_return
                    )

    def test_usergroup_update(self):
        """
        query_submitted = {"params": {"usrgrpid": 13, "users_status": 1}, "jsonrpc": "2.0",
        "id": 0, "auth": "ef772237245f59f655871bc8fbbcd67c", "method": "usergroup.update"}
        """

        module_return = ["13"]
        query_return = {"jsonrpc": "2.0", "result": {"usrgrpids": ["13"]}, "id": 0}

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.usergroup_update("13", users_status="1", **CONN_ARGS),
                    module_return,
                )

    def test_usergroup_list(self):
        """
        query_submitted = {"params": {"output": "extend"}, "jsonrpc": "2.0", "id": 0,
        "auth": "4bc366bc7803c07e80f15b1bc14dc61f", "method": "usergroup.get"}
        """

        module_return = [
            {
                "usrgrpid": "7",
                "gui_access": "0",
                "debug_mode": "0",
                "name": "Zabbix administrators",
                "users_status": "0",
            },
            {
                "usrgrpid": "8",
                "gui_access": "0",
                "debug_mode": "0",
                "name": "Guests",
                "users_status": "0",
            },
            {
                "usrgrpid": "9",
                "gui_access": "0",
                "debug_mode": "0",
                "name": "Disabled",
                "users_status": "1",
            },
            {
                "usrgrpid": "11",
                "gui_access": "0",
                "debug_mode": "1",
                "name": "Enabled debug mode",
                "users_status": "0",
            },
            {
                "usrgrpid": "12",
                "gui_access": "2",
                "debug_mode": "0",
                "name": "No access to the frontend",
                "users_status": "0",
            },
            {
                "usrgrpid": "13",
                "gui_access": "0",
                "debug_mode": "0",
                "name": "testgroup",
                "users_status": "0",
            },
        ]
        # pylint: disable=E8128
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "usrgrpid": "7",
                    "name": "Zabbix administrators",
                    "gui_access": "0",
                    "users_status": "0",
                    "debug_mode": "0",
                },
                {
                    "usrgrpid": "8",
                    "name": "Guests",
                    "gui_access": "0",
                    "users_status": "0",
                    "debug_mode": "0",
                },
                {
                    "usrgrpid": "9",
                    "name": "Disabled",
                    "gui_access": "0",
                    "users_status": "1",
                    "debug_mode": "0",
                },
                {
                    "usrgrpid": "11",
                    "name": "Enabled debug mode",
                    "gui_access": "0",
                    "users_status": "0",
                    "debug_mode": "1",
                },
                {
                    "usrgrpid": "12",
                    "name": "No access to the frontend",
                    "gui_access": "2",
                    "users_status": "0",
                    "debug_mode": "0",
                },
                {
                    "usrgrpid": "13",
                    "name": "testgroup",
                    "gui_access": "0",
                    "users_status": "0",
                    "debug_mode": "0",
                },
            ],
            "id": 0,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(zabbix.usergroup_list(**CONN_ARGS), module_return)

    def test_host_inventory_get(self):
        """
        test host_inventory_get
        """
        module_return = {
            "poc_2_email": "",
            "poc_2_phone_b": "",
            "site_country": "",
            "poc_2_screen": "",
            "poc_2_notes": "",
            "poc_1_screen": "",
            "hardware": "",
            "software_app_a": "",
            "software_app_b": "",
            "software_app_c": "",
            "software_app_d": "",
            "os_short": "",
            "site_zip": "",
            "poc_2_name": "",
            "os_full": "",
            "host_netmask": "",
            "host_router": "",
            "url_c": "",
            "date_hw_install": "",
            "poc_1_phone_b": "",
            "poc_1_phone_a": "",
            "poc_1_cell": "",
            "type_full": "",
            "location_lat": "",
            "vendor": "",
            "contact": "",
            "site_rack": "",
            "location": "",
            "poc_2_cell": "",
            "date_hw_expiry": "",
            "installer_name": "",
            "type": "",
            "contract_number": "",
            "deployment_status": "",
            "site_notes": "",
            "inventory_mode": "0",
            "oob_ip": "",
            "host_networks": "",
            "hardware_full": "",
            "poc_2_phone_a": "",
            "poc_1_name": "",
            "site_state": "",
            "chassis": "",
            "software_app_e": "",
            "site_address_b": "",
            "site_address_a": "",
            "date_hw_decomm": "",
            "date_hw_purchase": "",
            "location_lon": "",
            "hw_arch": "",
            "software_full": "",
            "asset_tag": "",
            "oob_router": "",
            "hostid": "10258",
            "poc_1_email": "",
            "name": "",
            "poc_1_notes": "",
            "serialno_b": "",
            "notes": "",
            "oob_netmask": "",
            "alias": "other thing",
            "tag": "",
            "macaddress_b": "",
            "macaddress_a": "",
            "site_city": "",
            "site_address_c": "",
            "model": "",
            "serialno_a": "",
            "os": "some",
            "url_b": "",
            "url_a": "",
            "software": "",
        }
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "hostid": "10258",
                    "proxy_hostid": "0",
                    "host": "master",
                    "status": "0",
                    "disable_until": "1517766661",
                    "error": (
                        "Get value from agent failed: cannot connect to"
                        " [[10.0.2.15]:10050]: [111] Connection refused"
                    ),
                    "available": "2",
                    "errors_from": "1516087871",
                    "lastaccess": "0",
                    "ipmi_authtype": "-1",
                    "ipmi_privilege": "2",
                    "ipmi_username": "",
                    "ipmi_password": "",
                    "ipmi_disable_until": "0",
                    "ipmi_available": "0",
                    "snmp_disable_until": "0",
                    "snmp_available": "0",
                    "maintenanceid": "0",
                    "maintenance_status": "0",
                    "maintenance_type": "0",
                    "maintenance_from": "0",
                    "ipmi_errors_from": "0",
                    "snmp_errors_from": "0",
                    "ipmi_error": "",
                    "snmp_error": "",
                    "jmx_disable_until": "0",
                    "jmx_available": "0",
                    "jmx_errors_from": "0",
                    "jmx_error": "",
                    "name": "master",
                    "flags": "0",
                    "templateid": "0",
                    "description": "",
                    "tls_connect": "1",
                    "tls_accept": "1",
                    "tls_issuer": "",
                    "tls_subject": "",
                    "tls_psk_identity": "",
                    "tls_psk": "",
                    "inventory": {
                        "hostid": "10258",
                        "inventory_mode": "0",
                        "type": "",
                        "type_full": "",
                        "name": "",
                        "alias": "other thing",
                        "os": "some",
                        "os_full": "",
                        "os_short": "",
                        "serialno_a": "",
                        "serialno_b": "",
                        "tag": "",
                        "asset_tag": "",
                        "macaddress_a": "",
                        "macaddress_b": "",
                        "hardware": "",
                        "hardware_full": "",
                        "software": "",
                        "software_full": "",
                        "software_app_a": "",
                        "software_app_b": "",
                        "software_app_c": "",
                        "software_app_d": "",
                        "software_app_e": "",
                        "contact": "",
                        "location": "",
                        "location_lat": "",
                        "location_lon": "",
                        "notes": "",
                        "chassis": "",
                        "model": "",
                        "hw_arch": "",
                        "vendor": "",
                        "contract_number": "",
                        "installer_name": "",
                        "deployment_status": "",
                        "url_a": "",
                        "url_b": "",
                        "url_c": "",
                        "host_networks": "",
                        "host_netmask": "",
                        "host_router": "",
                        "oob_ip": "",
                        "oob_netmask": "",
                        "oob_router": "",
                        "date_hw_purchase": "",
                        "date_hw_install": "",
                        "date_hw_expiry": "",
                        "date_hw_decomm": "",
                        "site_address_a": "",
                        "site_address_b": "",
                        "site_address_c": "",
                        "site_city": "",
                        "site_state": "",
                        "site_country": "",
                        "site_zip": "",
                        "site_rack": "",
                        "site_notes": "",
                        "poc_1_name": "",
                        "poc_1_email": "",
                        "poc_1_phone_a": "",
                        "poc_1_phone_b": "",
                        "poc_1_cell": "",
                        "poc_1_screen": "",
                        "poc_1_notes": "",
                        "poc_2_name": "",
                        "poc_2_email": "",
                        "poc_2_phone_a": "",
                        "poc_2_phone_b": "",
                        "poc_2_cell": "",
                        "poc_2_screen": "",
                        "poc_2_notes": "",
                    },
                }
            ],
            "id": 1,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.host_inventory_get("12345", **CONN_ARGS), module_return
                )

    def test_host_inventory_get_with_disabled_inventory(self):
        """
        test host_inventory_get with a host with inventory disabled
        """
        module_return = False
        query_return = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "hostid": "10258",
                    "proxy_hostid": "0",
                    "host": "master",
                    "status": "0",
                    "disable_until": "1517766661",
                    "error": "Get value from agent failed: cannot connect to [[10.0.2.15]:10050]: [111] Connection refused",
                    "available": "2",
                    "errors_from": "1516087871",
                    "lastaccess": "0",
                    "ipmi_authtype": "-1",
                    "ipmi_privilege": "2",
                    "ipmi_username": "",
                    "ipmi_password": "",
                    "ipmi_disable_until": "0",
                    "ipmi_available": "0",
                    "snmp_disable_until": "0",
                    "snmp_available": "0",
                    "maintenanceid": "0",
                    "maintenance_status": "0",
                    "maintenance_type": "0",
                    "maintenance_from": "0",
                    "ipmi_errors_from": "0",
                    "snmp_errors_from": "0",
                    "ipmi_error": "",
                    "snmp_error": "",
                    "jmx_disable_until": "0",
                    "jmx_available": "0",
                    "jmx_errors_from": "0",
                    "jmx_error": "",
                    "name": "master",
                    "flags": "0",
                    "templateid": "0",
                    "description": "",
                    "tls_connect": "1",
                    "tls_accept": "1",
                    "tls_issuer": "",
                    "tls_subject": "",
                    "tls_psk_identity": "",
                    "tls_psk": "",
                    "inventory": [],
                }
            ],
            "id": 1,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.host_inventory_get("12345", **CONN_ARGS), module_return
                )

    def test_host_inventory_get_with_a_missing_host(self):
        """
        test host_inventory_get with a non-existent host
        """
        module_return = False
        query_return = {
            "jsonrpc": "2.0",
            "result": [],
            "id": 0,
        }

        with patch.object(zabbix, "_query", return_value=query_return):
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.host_inventory_get("12345", **CONN_ARGS), module_return
                )

    def test_host_inventory_set(self):
        """
        query_submitted = {"params": {"hostid": 10258, "inventory_mode": "0", "inventory":
        {"asset_tag": "jml3322", "type": "Xen"}}, "jsonrpc": "2.0", "id": 0,
        "auth": "a50d2c3030b9b73d7c28b5ebd89c044c", "method": "host.update"}
        """

        module_return = {"hostids": [10258]}
        query_return = {"jsonrpc": "2.0", "result": {"hostids": [10258]}, "id": 0}
        with patch.object(
            zabbix, "_query", autospec=True, return_value=query_return
        ) as mock__query:
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.host_inventory_set(
                        10258, asset_tag="jml3322", type="Xen", **CONN_ARGS
                    ),
                    module_return,
                )
                mock__query.assert_called_with(
                    "host.update",
                    {
                        "hostid": 10258,
                        "inventory_mode": "0",
                        "inventory": {
                            "asset_tag": "jml3322",
                            "type": "Xen",
                            "url": "http://test.url",
                            "auth": "1234",
                        },
                    },
                    "http://test.url",
                    "1234",
                )

    def test_host_inventory_set_with_inventory_mode(self):
        """
        query_submitted = {"params": {"hostid": 10258, "inventory_mode": "1", "inventory":
        {"asset_tag": "jml3322", "type": "Xen"}}, "jsonrpc": "2.0", "id": 0,
        "auth": "a50d2c3030b9b73d7c28b5ebd89c044c", "method": "host.update"}
        """

        module_return = {"hostids": [10258]}
        query_return = {"jsonrpc": "2.0", "result": {"hostids": [10258]}, "id": 0}
        with patch.object(
            zabbix, "_query", autospec=True, return_value=query_return
        ) as mock__query:
            with patch.object(zabbix, "_login", return_value=CONN_ARGS):
                self.assertEqual(
                    zabbix.host_inventory_set(
                        10258,
                        asset_tag="jml3322",
                        type="Xen",
                        inventory_mode="1",
                        **CONN_ARGS
                    ),
                    module_return,
                )
                mock__query.assert_called_with(
                    "host.update",
                    {
                        "hostid": 10258,
                        "inventory_mode": "1",
                        "inventory": {
                            "asset_tag": "jml3322",
                            "type": "Xen",
                            "url": "http://test.url",
                            "auth": "1234",
                        },
                    },
                    "http://test.url",
                    "1234",
                )
