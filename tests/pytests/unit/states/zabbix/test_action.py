"""
    :codeauthor: :email:`Jakub Sliva <jakub.sliva@ultimum.io>`
"""

import pytest
import salt.states.zabbix_action as zabbix_action
from tests.support.mock import MagicMock, patch


@pytest.fixture
def input_params():
    return {
        "status": "0",
        "filter": {
            "evaltype": "2",
            "conditions": [
                {"operator": "2", "conditiontype": "24", "value": "database"}
            ],
        },
        "eventsource": "2",
        "name": "Auto registration Databases",
        "operations": [{"opgroup": [{"groupid": "6"}], "operationtype": "4"}],
    }


@pytest.fixture
def existing_obj():
    return [
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


@pytest.fixture
def existing_obj_diff():
    return {
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


@pytest.fixture
def diff_params():
    return {
        "filter": {
            "evaltype": "2",
            "conditions": [
                {"operator": "2", "conditiontype": "24", "value": "virtual"}
            ],
        },
        "actionid": "28",
    }


@pytest.fixture
def configure_loader_modules():
    return {zabbix_action: {}}


def test_present_create(input_params):
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
                    side_effect=[input_params, False]
                ),
                "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                "zabbix.compare_params": MagicMock(return_value={}),
            },
        ):
            ret["result"] = True
            ret["comment"] = 'Zabbix Action "{}" created.'.format(name)
            ret["changes"] = {
                name: {
                    "old": 'Zabbix Action "{}" did not exist.'.format(name),
                    "new": 'Zabbix Action "{}" created according definition.'.format(
                        name
                    ),
                }
            }
            assert zabbix_action.present(name, {}) == ret


def test_present_exists(input_params, existing_obj):
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
                    side_effect=[input_params, existing_obj]
                ),
                "zabbix.run_query": MagicMock(return_value=["length of result is 1"]),
                "zabbix.compare_params": MagicMock(return_value={}),
            },
        ):
            ret["result"] = True
            ret[
                "comment"
            ] = 'Zabbix Action "{}" already exists and corresponds to a definition.'.format(
                name
            )
            assert zabbix_action.present(name, {}) == ret


def test_present_update(input_params, existing_obj_diff, diff_params):
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
            return diff_params

    with patch.dict(zabbix_action.__opts__, {"test": False}):
        with patch.dict(
            zabbix_action.__salt__,
            {
                "zabbix.get_zabbix_id_mapper": MagicMock(
                    return_value={"action": "actionid"}
                ),
                "zabbix.substitute_params": MagicMock(
                    side_effect=[input_params, existing_obj_diff]
                ),
                "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                "zabbix.compare_params": MagicMock(return_value=diff_params),
            },
        ):
            ret["result"] = True
            ret["comment"] = 'Zabbix Action "{}" updated.'.format(name)
            ret["changes"] = {
                name: {
                    "old": (
                        'Zabbix Action "{}" differed '
                        "in following parameters: {}".format(name, diff_params)
                    ),
                    "new": 'Zabbix Action "{}" fixed.'.format(name),
                }
            }
            assert zabbix_action.present(name, {}) == ret


def test_absent_test_mode():
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
            ret["comment"] = 'Zabbix Action "{}" would be deleted.'.format(name)
            ret["changes"] = {
                name: {
                    "old": 'Zabbix Action "{}" exists.'.format(name),
                    "new": 'Zabbix Action "{}" would be deleted.'.format(name),
                }
            }
            assert zabbix_action.absent(name) == ret


def test_absent():
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
            ret["comment"] = 'Zabbix Action "{}" does not exist.'.format(name)
            assert zabbix_action.absent(name) == ret

        with patch.dict(
            zabbix_action.__salt__,
            {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
        ):
            with patch.dict(
                zabbix_action.__salt__,
                {"zabbix.run_query": MagicMock(return_value=True)},
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Action "{}" deleted.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Action "{}" existed.'.format(name),
                        "new": 'Zabbix Action "{}" deleted.'.format(name),
                    }
                }
                assert zabbix_action.absent(name) == ret
