# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Jakub Sliva <jakub.sliva@ultimum.io>`
"""

# Import Python Libs
from __future__ import absolute_import, unicode_literals

import salt.states.zabbix_action as zabbix_action

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

INPUT_PARAMS = {
    "status": "0",
    "filter": {
        "evaltype": "2",
        "conditions": [{"operator": "2", "conditiontype": "24", "value": "database"}],
    },
    "eventsource": "2",
    "name": "Auto registration Databases",
    "operations": [{"opgroup": [{"groupid": "6"}], "operationtype": "4"}],
}

EXISTING_OBJ = [
    {
        "status": "0",
        "operations": [
            {
                "operationtype": "4",
                "esc_period": "0",
                "evaltype": "0",
                "opconditions": [],
                "esc_step_to": "1",
                "actionid": "28",
                "esc_step_from": "1",
                "opgroup": [{"groupid": "6", "operationid": "92"}],
                "operationid": "92",
            }
        ],
        "def_shortdata": "",
        "name": "Auto registration Databases",
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
                    "value": "database",
                }
            ],
            "eval_formula": "A",
        },
        "eventsource": "2",
        "actionid": "28",
        "r_shortdata": "",
        "r_longdata": "",
        "recovery_msg": "0",
    }
]

EXISTING_OBJ_DIFF = {
    "status": "0",
    "operations": [
        {
            "operationtype": "4",
            "esc_period": "0",
            "evaltype": "0",
            "opconditions": [],
            "esc_step_to": "1",
            "actionid": "28",
            "esc_step_from": "1",
            "opgroup": [{"groupid": "6", "operationid": "92"}],
            "operationid": "92",
        }
    ],
    "def_shortdata": "",
    "name": "Auto registration Databases",
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
                "value": "SOME OTHER VALUE",
            }
        ],
        "eval_formula": "A",
    },
    "eventsource": "2",
    "actionid": "28",
    "r_shortdata": "",
    "r_longdata": "",
    "recovery_msg": "0",
}

DIFF_PARAMS = {
    "filter": {
        "evaltype": "2",
        "conditions": [{"operator": "2", "conditiontype": "24", "value": "virtual"}],
    },
    "actionid": "28",
}


class ZabbixActionTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.zabbix
    """

    def setup_loader_modules(self):
        return {zabbix_action: {}}

    def test_present_create(self):
        """
        Test to ensure that named action is created
        """
        name = "Auto registration Databases"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] == "action.get":
                return False
            elif args[0] == "action.create":
                return True

        with patch.dict(zabbix_action.__opts__, {"test": False}):
            with patch.dict(
                zabbix_action.__salt__,
                {
                    "zabbix.get_zabbix_id_mapper": MagicMock(
                        return_value={"action": "actionid"}
                    ),
                    "zabbix.substitute_params": MagicMock(
                        side_effect=[INPUT_PARAMS, False]
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(return_value={}),
                },
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Action "{0}" created.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Action "{0}" did not exist.'.format(name),
                        "new": 'Zabbix Action "{0}" created according definition.'.format(
                            name
                        ),
                    }
                }
                self.assertDictEqual(zabbix_action.present(name, {}), ret)

    def test_present_exists(self):
        """
        Test to ensure that named action is present and not changed
        """
        name = "Auto registration Databases"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        with patch.dict(zabbix_action.__opts__, {"test": False}):
            with patch.dict(
                zabbix_action.__salt__,
                {
                    "zabbix.get_zabbix_id_mapper": MagicMock(
                        return_value={"action": "actionid"}
                    ),
                    "zabbix.substitute_params": MagicMock(
                        side_effect=[INPUT_PARAMS, EXISTING_OBJ]
                    ),
                    "zabbix.run_query": MagicMock(
                        return_value=["length of result is 1"]
                    ),
                    "zabbix.compare_params": MagicMock(return_value={}),
                },
            ):
                ret["result"] = True
                ret[
                    "comment"
                ] = 'Zabbix Action "{0}" already exists and corresponds to a definition.'.format(
                    name
                )
                self.assertDictEqual(zabbix_action.present(name, {}), ret)

    def test_present_update(self):
        """
        Test to ensure that named action is present but must be updated
        """
        name = "Auto registration Databases"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] == "action.get":
                return ["length of result is 1 = action exists"]
            elif args[0] == "action.update":
                return DIFF_PARAMS

        with patch.dict(zabbix_action.__opts__, {"test": False}):
            with patch.dict(
                zabbix_action.__salt__,
                {
                    "zabbix.get_zabbix_id_mapper": MagicMock(
                        return_value={"action": "actionid"}
                    ),
                    "zabbix.substitute_params": MagicMock(
                        side_effect=[INPUT_PARAMS, EXISTING_OBJ_DIFF]
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(return_value=DIFF_PARAMS),
                },
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Action "{0}" updated.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Action "{0}" differed '
                        "in following parameters: {1}".format(name, DIFF_PARAMS),
                        "new": 'Zabbix Action "{0}" fixed.'.format(name),
                    }
                }
                self.assertDictEqual(zabbix_action.present(name, {}), ret)

    def test_absent_test_mode(self):
        """
        Test to ensure that named action is absent in test mode
        """
        name = "Auto registration Databases"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}
        with patch.dict(zabbix_action.__opts__, {"test": True}):
            with patch.dict(
                zabbix_action.__salt__,
                {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Action "{0}" would be deleted.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Action "{0}" exists.'.format(name),
                        "new": 'Zabbix Action "{0}" would be deleted.'.format(name),
                    }
                }
                self.assertDictEqual(zabbix_action.absent(name), ret)

    def test_absent(self):
        """
        Test to ensure that named action is absent
        """
        name = "Auto registration Databases"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}
        with patch.dict(zabbix_action.__opts__, {"test": False}):
            with patch.dict(
                zabbix_action.__salt__,
                {"zabbix.get_object_id_by_params": MagicMock(return_value=False)},
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Action "{0}" does not exist.'.format(name)
                self.assertDictEqual(zabbix_action.absent(name), ret)

            with patch.dict(
                zabbix_action.__salt__,
                {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
            ):
                with patch.dict(
                    zabbix_action.__salt__,
                    {"zabbix.run_query": MagicMock(return_value=True)},
                ):
                    ret["result"] = True
                    ret["comment"] = 'Zabbix Action "{0}" deleted.'.format(name)
                    ret["changes"] = {
                        name: {
                            "old": 'Zabbix Action "{0}" existed.'.format(name),
                            "new": 'Zabbix Action "{0}" deleted.'.format(name),
                        }
                    }
                    self.assertDictEqual(zabbix_action.absent(name), ret)
