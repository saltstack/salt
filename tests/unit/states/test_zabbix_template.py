# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Jakub Sliva <jakub.sliva@ultimum.io>`
"""

# Import Python Libs
from __future__ import absolute_import, unicode_literals

import salt.states.zabbix_template as zabbix_template

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

INPUT_PARAMS = {"applications": [{"name": "Ceph OSD"}]}

DEFINED_OBJ = {
    "macros": [{"macro": "{$CEPH_CLUSTER_NAME}", "value": "ceph"}],
    "host": "A Testing Template",
    "hosts": [{"hostid": "10112"}, {"hostid": "10113"}],
    "description": "Template for Ceph nodes",
    "groups": [{"groupid": "1"}],
}

DEFINED_C_LIST_SUBS = {
    "applications": [{"name": "Ceph OSD"}],
    "graphs": [],
    "triggers": [],
    "items": [],
    "httpTests": [],
    "screens": [],
    "gitems": [],
    "discoveries": [],
}

SUBSTITUTE_PARAMS_CREATE = [
    DEFINED_OBJ,
    [],
    DEFINED_C_LIST_SUBS["applications"],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
]

EXISTING_OBJ = [
    {
        "available": "0",
        "tls_connect": "1",
        "maintenance_type": "0",
        "groups": [{"groupid": "1"}],
        "macros": [
            {
                "macro": "{$CEPH_CLUSTER_NAME}",
                "hostmacroid": "60",
                "hostid": "10206",
                "value": "ceph",
            }
        ],
        "hosts": [{"hostid": "10112"}, {"hostid": "10113"}],
        "status": "3",
        "description": "Template for Ceph nodes",
        "host": "A Testing Template",
        "disable_until": "0",
        "templateid": "10206",
        "name": "A Testing Template",
    }
]

SUBSTITUTE_PARAMS_EXISTS = [
    DEFINED_OBJ,
    EXISTING_OBJ[0],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
]

EXISTING_OBJ_DIFF = [
    {
        "groups": [{"groupid": "1"}],
        "macros": [
            {
                "macro": "{$CEPH_CLUSTER_NAME}",
                "hostmacroid": "60",
                "hostid": "10206",
                "value": "ceph",
            }
        ],
        "hosts": [{"hostid": "10112"}, {"hostid": "10113"}],
        "status": "3",
        "templateid": "10206",
        "name": "A Testing Template",
    }
]

SUBSTITUTE_PARAMS_UPDATE = [
    DEFINED_OBJ,
    EXISTING_OBJ_DIFF[0],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
]

DIFF_PARAMS = {"old": {}, "new": {"macros": [], "templateid": "10206"}}


class ZabbixTemplateTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.zabbix
    """

    def setup_loader_modules(self):
        return {zabbix_template: {}}

    @patch("salt.states.zabbix_template.CHANGE_STACK", [])
    def test_present_create(self):
        """
        Test to ensure that named template is created
        """
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] == "template.get":
                return []
            elif args[0] == "template.create":
                return {"templateids": ["10206"]}
            elif args[0] == "application.get":
                return []
            elif args[0] == "application.create":
                return {"applicationids": ["701"]}

        with patch.dict(zabbix_template.__opts__, {"test": False}):
            with patch.dict(
                zabbix_template.__salt__,
                {
                    "zabbix.get_zabbix_id_mapper": MagicMock(
                        return_value={"template": "templateid"}
                    ),
                    "zabbix.substitute_params": MagicMock(
                        side_effect=SUBSTITUTE_PARAMS_CREATE
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(return_value={}),
                },
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Template "{0}" created.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Template "{0}" did not exist.'.format(name),
                        "new": 'Zabbix Template "{0}" created according definition.'.format(
                            name
                        ),
                    }
                }
                self.assertDictEqual(zabbix_template.present(name, {}), ret)

    @patch("salt.states.zabbix_template.CHANGE_STACK", [])
    def test_present_exists(self):
        """
        Test to ensure that named template is present and not changed
        """
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] == "template.get":
                return EXISTING_OBJ
            elif args[0] == "application.get":
                return ["non-empty"]

        with patch.dict(zabbix_template.__opts__, {"test": False}):
            with patch.dict(
                zabbix_template.__salt__,
                {
                    "zabbix.get_zabbix_id_mapper": MagicMock(
                        return_value={"template": "templateid"}
                    ),
                    "zabbix.substitute_params": MagicMock(
                        side_effect=SUBSTITUTE_PARAMS_EXISTS
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(
                        return_value={"new": {}, "old": {}}
                    ),
                },
            ):
                ret["result"] = True
                ret[
                    "comment"
                ] = 'Zabbix Template "{0}" already exists and corresponds to a definition.'.format(
                    name
                )
                self.assertDictEqual(zabbix_template.present(name, {}), ret)

    @patch("salt.states.zabbix_template.CHANGE_STACK", [])
    def test_present_update(self):
        """
        Test to ensure that named template is present but must be updated
        """
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] == "template.get":
                return ["length of result is 1 = template exists"]
            elif args[0] == "template.update":
                return DIFF_PARAMS

        with patch.dict(zabbix_template.__opts__, {"test": False}):
            with patch.dict(
                zabbix_template.__salt__,
                {
                    "zabbix.get_zabbix_id_mapper": MagicMock(
                        return_value={"template": "templateid"}
                    ),
                    "zabbix.substitute_params": MagicMock(
                        side_effect=SUBSTITUTE_PARAMS_UPDATE
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(return_value=DIFF_PARAMS),
                },
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Template "{0}" updated.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Template "{0}" differed.'.format(name),
                        "new": 'Zabbix Template "{0}" updated according definition.'.format(
                            name
                        ),
                    }
                }
                self.assertDictEqual(zabbix_template.present(name, {}), ret)

    def test_absent_test_mode(self):
        """
        Test to ensure that named template is absent in test mode
        """
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}
        with patch.dict(zabbix_template.__opts__, {"test": True}):
            with patch.dict(
                zabbix_template.__salt__,
                {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Template "{0}" would be deleted.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Template "{0}" exists.'.format(name),
                        "new": 'Zabbix Template "{0}" would be deleted.'.format(name),
                    }
                }
                self.assertDictEqual(zabbix_template.absent(name), ret)

    def test_absent(self):
        """
        Test to ensure that named template is absent
        """
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}
        with patch.dict(zabbix_template.__opts__, {"test": False}):
            with patch.dict(
                zabbix_template.__salt__,
                {"zabbix.get_object_id_by_params": MagicMock(return_value=False)},
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Template "{0}" does not exist.'.format(name)
                self.assertDictEqual(zabbix_template.absent(name), ret)

            with patch.dict(
                zabbix_template.__salt__,
                {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
            ):
                with patch.dict(
                    zabbix_template.__salt__,
                    {"zabbix.run_query": MagicMock(return_value=True)},
                ):
                    ret["result"] = True
                    ret["comment"] = 'Zabbix Template "{0}" deleted.'.format(name)
                    ret["changes"] = {
                        name: {
                            "old": 'Zabbix Template "{0}" existed.'.format(name),
                            "new": 'Zabbix Template "{0}" deleted.'.format(name),
                        }
                    }
                    self.assertDictEqual(zabbix_template.absent(name), ret)
