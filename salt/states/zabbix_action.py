# -*- coding: utf-8 -*-
"""
.. versionadded:: 2017.7

Management of Zabbix Action object over Zabbix API.

:codeauthor: Jakub Sliva <jakub.sliva@ultimum.io>
"""
from __future__ import absolute_import, unicode_literals

import json
import logging

try:
    from salt.ext import six
    from salt.exceptions import SaltException

    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False


log = logging.getLogger(__name__)


def __virtual__():
    """
    Only make these states available if Zabbix module and run_query function is available
    and all 3rd party modules imported.
    """
    if "zabbix.run_query" in __salt__ and IMPORTS_OK:
        return True
    return False, "Import zabbix or other needed modules failed."


def present(name, params, **kwargs):
    """
    Creates Zabbix Action object or if differs update it according defined parameters

    :param name: Zabbix Action name
    :param params: Definition of the Zabbix Action
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    If there is a need to get a value from current zabbix online (e.g. id of a hostgroup you want to put a discovered
    system into), put a dictionary with two keys "query_object" and "query_name" instead of the value.
    In this example we want to get object id of hostgroup named "Virtual machines" and "Databases".

    .. code-block:: yaml

        zabbix-action-present:
            zabbix_action.present:
                - name: VMs
                - params:
                    eventsource: 2
                    status: 0
                    filter:
                        evaltype: 2
                        conditions:
                            - conditiontype: 24
                              operator: 2
                              value: 'virtual'
                            - conditiontype: 24
                              operator: 2
                              value: 'kvm'
                    operations:
                        - operationtype: 2
                        - operationtype: 4
                          opgroup:
                              - groupid:
                                  query_object: hostgroup
                                  query_name: Virtual machines
                              - groupid:
                                  query_object: hostgroup
                                  query_name: Databases
    """
    zabbix_id_mapper = __salt__["zabbix.get_zabbix_id_mapper"]()

    dry_run = __opts__["test"]
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    # Create input params substituting functions with their results
    params["name"] = name
    params["operations"] = params["operations"] if "operations" in params else []
    if "filter" in params:
        params["filter"]["conditions"] = (
            params["filter"]["conditions"] if "conditions" in params["filter"] else []
        )

    input_params = __salt__["zabbix.substitute_params"](params, **kwargs)
    log.info(
        "Zabbix Action: input params: %s",
        six.text_type(json.dumps(input_params, indent=4)),
    )

    search = {
        "output": "extend",
        "selectOperations": "extend",
        "selectFilter": "extend",
        "filter": {"name": name},
    }
    # GET Action object if exists
    action_get = __salt__["zabbix.run_query"]("action.get", search, **kwargs)
    log.info(
        "Zabbix Action: action.get result: %s",
        six.text_type(json.dumps(action_get, indent=4)),
    )

    existing_obj = (
        __salt__["zabbix.substitute_params"](action_get[0], **kwargs)
        if action_get and len(action_get) == 1
        else False
    )

    if existing_obj:
        diff_params = __salt__["zabbix.compare_params"](input_params, existing_obj)
        log.info(
            "Zabbix Action: input params: {%s",
            six.text_type(json.dumps(input_params, indent=4)),
        )
        log.info(
            "Zabbix Action: Object comparison result. Differences: %s",
            six.text_type(diff_params),
        )

        if diff_params:
            diff_params[zabbix_id_mapper["action"]] = existing_obj[
                zabbix_id_mapper["action"]
            ]
            # diff_params['name'] = 'VMs' - BUG - https://support.zabbix.com/browse/ZBX-12078
            log.info(
                "Zabbix Action: update params: %s",
                six.text_type(json.dumps(diff_params, indent=4)),
            )

            if dry_run:
                ret["result"] = True
                ret["comment"] = 'Zabbix Action "{0}" would be fixed.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Action "{0}" differs '
                        "in following parameters: {1}".format(name, diff_params),
                        "new": 'Zabbix Action "{0}" would correspond to definition.'.format(
                            name
                        ),
                    }
                }
            else:
                action_update = __salt__["zabbix.run_query"](
                    "action.update", diff_params, **kwargs
                )
                log.info(
                    "Zabbix Action: action.update result: %s",
                    six.text_type(action_update),
                )
                if action_update:
                    ret["result"] = True
                    ret["comment"] = 'Zabbix Action "{0}" updated.'.format(name)
                    ret["changes"] = {
                        name: {
                            "old": 'Zabbix Action "{0}" differed '
                            "in following parameters: {1}".format(name, diff_params),
                            "new": 'Zabbix Action "{0}" fixed.'.format(name),
                        }
                    }

        else:
            ret["result"] = True
            ret[
                "comment"
            ] = 'Zabbix Action "{0}" already exists and corresponds to a definition.'.format(
                name
            )

    else:
        if dry_run:
            ret["result"] = True
            ret["comment"] = 'Zabbix Action "{0}" would be created.'.format(name)
            ret["changes"] = {
                name: {
                    "old": 'Zabbix Action "{0}" does not exist.'.format(name),
                    "new": 'Zabbix Action "{0}" would be created according definition.'.format(
                        name
                    ),
                }
            }
        else:
            # ACTION.CREATE
            action_create = __salt__["zabbix.run_query"](
                "action.create", input_params, **kwargs
            )
            log.info(
                "Zabbix Action: action.create result: %s", six.text_type(action_create)
            )

            if action_create:
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

    return ret


def absent(name, **kwargs):
    """
    Makes the Zabbix Action to be absent (either does not exist or delete it).

    :param name: Zabbix Action name
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        zabbix-action-absent:
            zabbix_action.absent:
                - name: Action name
    """
    dry_run = __opts__["test"]
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    try:
        object_id = __salt__["zabbix.get_object_id_by_params"](
            "action", {"filter": {"name": name}}, **kwargs
        )
    except SaltException:
        object_id = False

    if not object_id:
        ret["result"] = True
        ret["comment"] = 'Zabbix Action "{0}" does not exist.'.format(name)
    else:
        if dry_run:
            ret["result"] = True
            ret["comment"] = 'Zabbix Action "{0}" would be deleted.'.format(name)
            ret["changes"] = {
                name: {
                    "old": 'Zabbix Action "{0}" exists.'.format(name),
                    "new": 'Zabbix Action "{0}" would be deleted.'.format(name),
                }
            }
        else:
            action_delete = __salt__["zabbix.run_query"](
                "action.delete", [object_id], **kwargs
            )

            if action_delete:
                ret["result"] = True
                ret["comment"] = 'Zabbix Action "{0}" deleted.'.format(name)
                ret["changes"] = {
                    name: {
                        "old": 'Zabbix Action "{0}" existed.'.format(name),
                        "new": 'Zabbix Action "{0}" deleted.'.format(name),
                    }
                }

    return ret
