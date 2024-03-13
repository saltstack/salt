"""
Management of Zabbix Action object over Zabbix API.

.. versionadded:: 2017.7.0

:codeauthor: Jakub Sliva <jakub.sliva@ultimum.io>
"""

import json
import logging

from salt.exceptions import SaltException

log = logging.getLogger(__name__)

__deprecated__ = (
    3009,
    "zabbix",
    "https://github.com/salt-extensions/saltext-zabbix",
)


def __virtual__():
    """
    Only make these states available if Zabbix module and run_query function is available
    and all 3rd party modules imported.
    """
    if "zabbix.run_query" in __salt__:
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
        str(json.dumps(input_params, indent=4)),
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
        str(json.dumps(action_get, indent=4)),
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
            str(json.dumps(input_params, indent=4)),
        )
        log.info(
            "Zabbix Action: Object comparison result. Differences: %s",
            str(diff_params),
        )

        if diff_params:
            diff_params[zabbix_id_mapper["action"]] = existing_obj[
                zabbix_id_mapper["action"]
            ]
            # diff_params['name'] = 'VMs' - BUG - https://support.zabbix.com/browse/ZBX-12078
            log.info(
                "Zabbix Action: update params: %s",
                str(json.dumps(diff_params, indent=4)),
            )

            if dry_run:
                ret["result"] = True
                ret["comment"] = f'Zabbix Action "{name}" would be fixed.'
                ret["changes"] = {
                    name: {
                        "old": (
                            'Zabbix Action "{}" differs '
                            "in following parameters: {}".format(name, diff_params)
                        ),
                        "new": (
                            'Zabbix Action "{}" would correspond to definition.'.format(
                                name
                            )
                        ),
                    }
                }
            else:
                action_update = __salt__["zabbix.run_query"](
                    "action.update", diff_params, **kwargs
                )
                log.info(
                    "Zabbix Action: action.update result: %s",
                    str(action_update),
                )
                if action_update:
                    ret["result"] = True
                    ret["comment"] = f'Zabbix Action "{name}" updated.'
                    ret["changes"] = {
                        name: {
                            "old": (
                                'Zabbix Action "{}" differed '
                                "in following parameters: {}".format(name, diff_params)
                            ),
                            "new": f'Zabbix Action "{name}" fixed.',
                        }
                    }

        else:
            ret["result"] = True
            ret["comment"] = (
                'Zabbix Action "{}" already exists and corresponds to a definition.'.format(
                    name
                )
            )

    else:
        if dry_run:
            ret["result"] = True
            ret["comment"] = f'Zabbix Action "{name}" would be created.'
            ret["changes"] = {
                name: {
                    "old": f'Zabbix Action "{name}" does not exist.',
                    "new": (
                        'Zabbix Action "{}" would be created according definition.'.format(
                            name
                        )
                    ),
                }
            }
        else:
            # ACTION.CREATE
            action_create = __salt__["zabbix.run_query"](
                "action.create", input_params, **kwargs
            )
            log.info("Zabbix Action: action.create result: %s", str(action_create))

            if action_create:
                ret["result"] = True
                ret["comment"] = f'Zabbix Action "{name}" created.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Action "{name}" did not exist.',
                        "new": (
                            'Zabbix Action "{}" created according definition.'.format(
                                name
                            )
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
        ret["comment"] = f'Zabbix Action "{name}" does not exist.'
    else:
        if dry_run:
            ret["result"] = True
            ret["comment"] = f'Zabbix Action "{name}" would be deleted.'
            ret["changes"] = {
                name: {
                    "old": f'Zabbix Action "{name}" exists.',
                    "new": f'Zabbix Action "{name}" would be deleted.',
                }
            }
        else:
            action_delete = __salt__["zabbix.run_query"](
                "action.delete", [object_id], **kwargs
            )

            if action_delete:
                ret["result"] = True
                ret["comment"] = f'Zabbix Action "{name}" deleted.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Action "{name}" existed.',
                        "new": f'Zabbix Action "{name}" deleted.',
                    }
                }

    return ret
