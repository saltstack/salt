"""
    :codeauthor: :email:`Jakub Sliva <jakub.sliva@ultimum.io>`
"""

import pytest

import salt.states.zabbix_valuemap as zabbix_valuemap
from tests.support.mock import MagicMock, patch


@pytest.fixture
def input_params():
    return {
        "mappings": [
            {"newvalue": "OK", "value": "0h"},
            {"newvalue": "Failure", "value": "1"},
        ],
        "name": "Server HP Health",
    }


@pytest.fixture
def existing_obj():
    return [
        {
            "valuemapid": "21",
            "name": "Server HP Health",
            "mappings": [
                {"newvalue": "OK", "value": "0h"},
                {"newvalue": "Failure", "value": "1"},
            ],
        }
    ]


@pytest.fixture
def existing_obj_diff():
    return {
        "valuemapid": "21",
        "name": "Server HP Health",
        "mappings": [
            {"newvalue": "OK", "value": "0h"},
            {"newvalue": "Failure", "value": "1"},
            {"newvalue": "some", "value": "2"},
        ],
    }


@pytest.fixture
def diff_params():
    return {
        "valuemapid": "21",
        "mappings": [
            {"newvalue": "OK", "value": "0h"},
            {"newvalue": "Failure", "value": "1"},
        ],
    }


@pytest.fixture
def configure_loader_modules():
    return {zabbix_valuemap: {}}


def test_present_create(input_params):
    """
    Test to ensure that named value map is created
    """
    name = "Server HP Health"
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    def side_effect_run_query(*args):
        """
        Differentiate between __salt__ exec module function calls with different parameters.
        """
        if args[0] == "valuemap.get":
            return False
        elif args[0] == "valuemap.create":
            return True

    with patch.dict(zabbix_valuemap.__opts__, {"test": False}):
        with patch.dict(
            zabbix_valuemap.__salt__,
            {
                "zabbix.get_zabbix_id_mapper": MagicMock(
                    return_value={"valuemap": "valuemapid"}
                ),
                "zabbix.substitute_params": MagicMock(
                    side_effect=[input_params, False]
                ),
                "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                "zabbix.compare_params": MagicMock(return_value={}),
            },
        ):
            ret["result"] = True
            ret["comment"] = f'Zabbix Value map "{name}" created.'
            ret["changes"] = {
                name: {
                    "old": f'Zabbix Value map "{name}" did not exist.',
                    "new": 'Zabbix Value map "{}" created according definition.'.format(
                        name
                    ),
                }
            }
            assert zabbix_valuemap.present(name, {}) == ret


def test_present_exists(input_params, existing_obj):
    """
    Test to ensure that named value map is present and not changed
    """
    name = "Server HP Health"
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    with patch.dict(zabbix_valuemap.__opts__, {"test": False}):
        with patch.dict(
            zabbix_valuemap.__salt__,
            {
                "zabbix.get_zabbix_id_mapper": MagicMock(
                    return_value={"valuemap": "valuemapid"}
                ),
                "zabbix.substitute_params": MagicMock(
                    side_effect=[input_params, existing_obj]
                ),
                "zabbix.run_query": MagicMock(return_value=["length of result is 1"]),
                "zabbix.compare_params": MagicMock(return_value={}),
            },
        ):
            ret["result"] = True
            ret["comment"] = (
                'Zabbix Value map "{}" already exists and corresponds to a definition.'.format(
                    name
                )
            )
            assert zabbix_valuemap.present(name, {}) == ret


def test_present_update(input_params, existing_obj_diff, diff_params):
    """
    Test to ensure that named value map is present but must be updated
    """
    name = "Server HP Health"
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    def side_effect_run_query(*args):
        """
        Differentiate between __salt__ exec module function calls with different parameters.
        """
        if args[0] == "valuemap.get":
            return ["length of result is 1 = valuemap exists"]
        elif args[0] == "valuemap.update":
            return diff_params

    with patch.dict(zabbix_valuemap.__opts__, {"test": False}):
        with patch.dict(
            zabbix_valuemap.__salt__,
            {
                "zabbix.get_zabbix_id_mapper": MagicMock(
                    return_value={"valuemap": "valuemapid"}
                ),
                "zabbix.substitute_params": MagicMock(
                    side_effect=[input_params, existing_obj_diff]
                ),
                "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                "zabbix.compare_params": MagicMock(return_value=diff_params),
            },
        ):
            ret["result"] = True
            ret["comment"] = f'Zabbix Value map "{name}" updated.'
            ret["changes"] = {
                name: {
                    "old": (
                        'Zabbix Value map "{}" differed '
                        "in following parameters: {}".format(name, diff_params)
                    ),
                    "new": f'Zabbix Value map "{name}" fixed.',
                }
            }
            assert zabbix_valuemap.present(name, {}) == ret


def test_absent_test_mode():
    """
    Test to ensure that named value map is absent in test mode
    """
    name = "Server HP Health"
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    with patch.dict(zabbix_valuemap.__opts__, {"test": True}):
        with patch.dict(
            zabbix_valuemap.__salt__,
            {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
        ):
            ret["result"] = True
            ret["comment"] = f'Zabbix Value map "{name}" would be deleted.'
            ret["changes"] = {
                name: {
                    "old": f'Zabbix Value map "{name}" exists.',
                    "new": f'Zabbix Value map "{name}" would be deleted.',
                }
            }
            assert zabbix_valuemap.absent(name) == ret


def test_absent():
    """
    Test to ensure that named value map is absent
    """
    name = "Server HP Health"
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    with patch.dict(zabbix_valuemap.__opts__, {"test": False}):
        with patch.dict(
            zabbix_valuemap.__salt__,
            {"zabbix.get_object_id_by_params": MagicMock(return_value=False)},
        ):
            ret["result"] = True
            ret["comment"] = f'Zabbix Value map "{name}" does not exist.'
            assert zabbix_valuemap.absent(name) == ret

        with patch.dict(
            zabbix_valuemap.__salt__,
            {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
        ):
            with patch.dict(
                zabbix_valuemap.__salt__,
                {"zabbix.run_query": MagicMock(return_value=True)},
            ):
                ret["result"] = True
                ret["comment"] = f'Zabbix Value map "{name}" deleted.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Value map "{name}" existed.',
                        "new": f'Zabbix Value map "{name}" deleted.',
                    }
                }
                assert zabbix_valuemap.absent(name) == ret
