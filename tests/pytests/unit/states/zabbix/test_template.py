"""
    :codeauthor: :email:`Jakub Sliva <jakub.sliva@ultimum.io>`
"""

import pytest
import salt.states.zabbix_template as zabbix_template
from tests.support.mock import MagicMock, patch


@pytest.fixture
def defined_obj():
    return {
        "macros": [{"macro": "{$CEPH_CLUSTER_NAME}", "value": "ceph"}],
        "host": "A Testing Template",
        "hosts": [{"hostid": "10112"}, {"hostid": "10113"}],
        "description": "Template for Ceph nodes",
        "groups": [{"groupid": "1"}],
    }


@pytest.fixture
def defined_c_list_subs():
    return {
        "applications": [{"name": "Ceph OSD"}],
        "graphs": [],
        "triggers": [],
        "items": [],
        "httpTests": [],
        "screens": [],
        "gitems": [],
        "discoveries": [],
    }


@pytest.fixture
def substitute_params_create(defined_obj, defined_c_list_subs):
    return [
        defined_obj,
        [],
        defined_c_list_subs["applications"],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    ]


@pytest.fixture
def existing_obj():
    return [
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


@pytest.fixture
def substitute_params_exists(defined_obj, existing_obj):
    return [
        defined_obj,
        existing_obj[0],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    ]


@pytest.fixture
def existing_obj_diff():
    return [
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


@pytest.fixture
def substitute_params_update(defined_obj, existing_obj_diff):
    return [
        defined_obj,
        existing_obj_diff[0],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    ]


@pytest.fixture
def diff_params():
    return {"old": {}, "new": {"macros": [], "templateid": "10206"}}


@pytest.fixture
def configure_loader_modules():
    return {zabbix_template: {}}


def test_present_create(substitute_params_create):
    """
    Test to ensure that named template is created
    """
    with patch("salt.states.zabbix_template.CHANGE_STACK", []):
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] in ("template.get", "application.get"):
                return []
            elif args[0] == "template.create":
                return {"templateids": ["10206"]}
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
                        side_effect=substitute_params_create
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(return_value={}),
                },
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Template "{}" created.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Template "{}" did not exist.'.format(name),
                        "new": (
                            'Zabbix Template "{}" created according definition.'.format(
                                name
                            )
                        ),
                    }
                }
                assert zabbix_template.present(name, {}) == ret


def test_present_exists(existing_obj, substitute_params_exists):
    """
    Test to ensure that named template is present and not changed
    """
    with patch("salt.states.zabbix_template.CHANGE_STACK", []):
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] == "template.get":
                return existing_obj
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
                        side_effect=substitute_params_exists
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(
                        return_value={"new": {}, "old": {}}
                    ),
                },
            ):
                ret["result"] = True
                ret["comment"] = (
                    'Zabbix Template "{}" already exists and corresponds to a'
                    " definition.".format(name)
                )
                assert zabbix_template.present(name, {}) == ret


def test_present_update(diff_params, substitute_params_update):
    """
    Test to ensure that named template is present but must be updated
    """
    with patch("salt.states.zabbix_template.CHANGE_STACK", []):
        name = "A Testing Template"
        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        def side_effect_run_query(*args):
            """
            Differentiate between __salt__ exec module function calls with different parameters.
            """
            if args[0] == "template.get":
                return ["length of result is 1 = template exists"]
            elif args[0] == "template.update":
                return diff_params

        with patch.dict(zabbix_template.__opts__, {"test": False}):
            with patch.dict(
                zabbix_template.__salt__,
                {
                    "zabbix.get_zabbix_id_mapper": MagicMock(
                        return_value={"template": "templateid"}
                    ),
                    "zabbix.substitute_params": MagicMock(
                        side_effect=substitute_params_update
                    ),
                    "zabbix.run_query": MagicMock(side_effect=side_effect_run_query),
                    "zabbix.compare_params": MagicMock(return_value=diff_params),
                },
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Template "{}" updated.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Template "{}" differed.'.format(name),
                        "new": (
                            'Zabbix Template "{}" updated according definition.'.format(
                                name
                            )
                        ),
                    }
                }
                assert zabbix_template.present(name, {}) == ret


def test_absent_test_mode():
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
            ret["comment"] = 'Zabbix Template "{}" would be deleted.'.format(name)
            ret["changes"] = {
                name: {
                    "old": 'Zabbix Template "{}" exists.'.format(name),
                    "new": 'Zabbix Template "{}" would be deleted.'.format(name),
                }
            }
            assert zabbix_template.absent(name) == ret


def test_absent():
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
            ret["comment"] = 'Zabbix Template "{}" does not exist.'.format(name)
            assert zabbix_template.absent(name) == ret

        with patch.dict(
            zabbix_template.__salt__,
            {"zabbix.get_object_id_by_params": MagicMock(return_value=11)},
        ):
            with patch.dict(
                zabbix_template.__salt__,
                {"zabbix.run_query": MagicMock(return_value=True)},
            ):
                ret["result"] = True
                ret["comment"] = 'Zabbix Template "{}" deleted.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Template "{}" existed.'.format(name),
                        "new": 'Zabbix Template "{}" deleted.'.format(name),
                    }
                }
                assert zabbix_template.absent(name) == ret
