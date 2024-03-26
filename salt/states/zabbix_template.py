"""
.. versionadded:: 2017.7.0

Management of Zabbix Template object over Zabbix API.

:codeauthor: Jakub Sliva <jakub.sliva@ultimum.io>
"""

import json
import logging

from salt.exceptions import SaltException

log = logging.getLogger(__name__)

TEMPLATE_RELATIONS = ["groups", "hosts", "macros"]
TEMPLATE_COMPONENT_ORDER = (
    "applications",
    "items",
    "gitems",
    "graphs",
    "screens",
    "httpTests",
    "triggers",
    "discoveries",
)
DISCOVERYRULE_COMPONENT_ORDER = (
    "itemprototypes",
    "triggerprototypes",
    "graphprototypes",
    "hostprototypes",
)
TEMPLATE_COMPONENT_DEF = {
    # 'component': {'qtype':        'component type to query',
    #               'qidname':      'component id name',
    #               'qselectpid':   'particular component selection attribute name (parent id name)',
    #               'ptype':        'parent component type',
    #               'pid':          'parent component id',
    #               'pid_ref_name': 'component's creation reference name for parent id',
    #               'res_id_name':  'jsonrpc modification call result key name of list of affected IDs'},
    #               'output':       {'output': 'extend', 'selectApplications': 'extend', 'templated': 'true'},
    #               'inherited':    'attribute name for inheritance toggling',
    #               'filter':       'child component unique identification attribute name',
    "applications": {
        "qtype": "application",
        "qidname": "applicationid",
        "qselectpid": "templateids",
        "ptype": "template",
        "pid": "templateid",
        "pid_ref_name": "hostid",
        "res_id_name": "applicationids",
        "output": {"output": "extend", "templated": "true"},
        "inherited": "inherited",
        "adjust": True,
        "filter": "name",
        "ro_attrs": ["applicationid", "flags", "templateids"],
    },
    "items": {
        "qtype": "item",
        "qidname": "itemid",
        "qselectpid": "templateids",
        "ptype": "template",
        "pid": "templateid",
        "pid_ref_name": "hostid",
        "res_id_name": "itemids",
        "output": {
            "output": "extend",
            "selectApplications": "extend",
            "templated": "true",
        },
        "inherited": "inherited",
        "adjust": False,
        "filter": "name",
        "ro_attrs": [
            "itemid",
            "error",
            "flags",
            "lastclock",
            "lastns",
            "lastvalue",
            "prevvalue",
            "state",
            "templateid",
        ],
    },
    "triggers": {
        "qtype": "trigger",
        "qidname": "triggerid",
        "qselectpid": "templateids",
        "ptype": "template",
        "pid": "templateid",
        "pid_ref_name": None,
        "res_id_name": "triggerids",
        "output": {
            "output": "extend",
            "selectDependencies": "expand",
            "templated": "true",
            "expandExpression": "true",
        },
        "inherited": "inherited",
        "adjust": False,
        "filter": "description",
        "ro_attrs": ["error", "flags", "lastchange", "state", "templateid", "value"],
    },
    "graphs": {
        "qtype": "graph",
        "qidname": "graphid",
        "qselectpid": "templateids",
        "ptype": "template",
        "pid": "templateid",
        "pid_ref_name": None,
        "res_id_name": "graphids",
        "output": {
            "output": "extend",
            "selectGraphItems": "extend",
            "templated": "true",
        },
        "inherited": "inherited",
        "adjust": False,
        "filter": "name",
        "ro_attrs": ["graphid", "flags", "templateid"],
    },
    "gitems": {
        "qtype": "graphitem",
        "qidname": "itemid",
        "qselectpid": "graphids",
        "ptype": "graph",
        "pid": "graphid",
        "pid_ref_name": None,
        "res_id_name": None,
        "output": {"output": "extend"},
        "inherited": "inherited",
        "adjust": False,
        "filter": "name",
        "ro_attrs": ["gitemid"],
    },
    # "Template screen"
    "screens": {
        "qtype": "templatescreen",
        "qidname": "screenid",
        "qselectpid": "templateids",
        "ptype": "template",
        "pid": "templateid",
        "pid_ref_name": "templateid",
        "res_id_name": "screenids",
        "output": {
            "output": "extend",
            "selectUsers": "extend",
            "selectUserGroups": "extend",
            "selectScreenItems": "extend",
            "noInheritance": "true",
        },
        "inherited": "noInheritance",
        "adjust": False,
        "filter": "name",
        "ro_attrs": ["screenid"],
    },
    # "LLD rule"
    "discoveries": {
        "qtype": "discoveryrule",
        "qidname": "itemid",
        "qselectpid": "templateids",
        "ptype": "template",
        "pid": "templateid",
        "pid_ref_name": "hostid",
        "res_id_name": "itemids",
        "output": {"output": "extend", "selectFilter": "extend", "templated": "true"},
        "inherited": "inherited",
        "adjust": False,
        "filter": "key_",
        "ro_attrs": ["itemid", "error", "state", "templateid"],
    },
    # "Web scenario"
    "httpTests": {
        "qtype": "httptest",
        "qidname": "httptestid",
        "qselectpid": "templateids",
        "ptype": "template",
        "pid": "templateid",
        "pid_ref_name": "hostid",
        "res_id_name": "httptestids",
        "output": {"output": "extend", "selectSteps": "extend", "templated": "true"},
        "inherited": "inherited",
        "adjust": False,
        "filter": "name",
        "ro_attrs": ["httptestid", "nextcheck", "templateid"],
    },
    # discoveries => discoveryrule
    "itemprototypes": {
        "qtype": "itemprototype",
        "qidname": "itemid",
        "qselectpid": "discoveryids",
        "ptype": "discoveryrule",
        "pid": "itemid",
        "pid_ref_name": "ruleid",
        # exception only in case of itemprototype - needs both parent ruleid and hostid
        "pid_ref_name2": "hostid",
        "res_id_name": "itemids",
        "output": {
            "output": "extend",
            "selectSteps": "extend",
            "selectApplications": "extend",
            "templated": "true",
        },
        "adjust": False,
        "inherited": "inherited",
        "filter": "name",
        "ro_attrs": ["itemid", "templateid"],
    },
    "triggerprototypes": {
        "qtype": "triggerprototype",
        "qidname": "triggerid",
        "qselectpid": "discoveryids",
        "ptype": "discoveryrule",
        "pid": "itemid",
        "pid_ref_name": None,
        "res_id_name": "triggerids",
        "output": {
            "output": "extend",
            "selectTags": "extend",
            "selectDependencies": "extend",
            "templated": "true",
            "expandExpression": "true",
        },
        "inherited": "inherited",
        "adjust": False,
        "filter": "description",
        "ro_attrs": ["triggerid", "templateid"],
    },
    "graphprototypes": {
        "qtype": "graphprototype",
        "qidname": "graphid",
        "qselectpid": "discoveryids",
        "ptype": "discoveryrule",
        "pid": "itemid",
        "pid_ref_name": None,
        "res_id_name": "graphids",
        "output": {
            "output": "extend",
            "selectGraphItems": "extend",
            "templated": "true",
        },
        "inherited": "inherited",
        "adjust": False,
        "filter": "name",
        "ro_attrs": ["graphid", "templateid"],
    },
    "hostprototypes": {
        "qtype": "hostprototype",
        "qidname": "hostid",
        "qselectpid": "discoveryids",
        "ptype": "discoveryrule",
        "pid": "itemid",
        "pid_ref_name": "ruleid",
        "res_id_name": "hostids",
        "output": {
            "output": "extend",
            "selectGroupLinks": "expand",
            "selectGroupPrototypes": "expand",
            "selectTemplates": "expand",
        },
        "inherited": "inherited",
        "adjust": False,
        "filter": "host",
        "ro_attrs": ["hostid", "templateid"],
    },
}

# CHANGE_STACK = [{'component': 'items', 'action': 'create', 'params': dict|list}]
CHANGE_STACK = []


def __virtual__():
    """
    Only make these states available if Zabbix module and run_query function is available
    and all 3rd party modules imported.
    """
    if "zabbix.run_query" in __salt__:
        return True
    return False, "Import zabbix or other needed modules failed."


def _diff_and_merge_host_list(defined, existing):
    """
    If Zabbix template is to be updated then list of assigned hosts must be provided in all or nothing manner to prevent
    some externally assigned hosts to be detached.

    :param defined: list of hosts defined in sls
    :param existing: list of hosts taken from live Zabbix
    :return: list to be updated (combinated or empty list)
    """
    try:
        defined_host_ids = {host["hostid"] for host in defined}
        existing_host_ids = {host["hostid"] for host in existing}
    except KeyError:
        raise SaltException("List of hosts in template not defined correctly.")

    diff = defined_host_ids - existing_host_ids
    return (
        [{"hostid": str(hostid)} for hostid in diff | existing_host_ids] if diff else []
    )


def _get_existing_template_c_list(component, parent_id, **kwargs):
    """
    Make a list of given component type not inherited from other templates because Zabbix API returns only list of all
    and list of inherited component items so we have to do a difference list.

    :param component: Template component (application, item, etc...)
    :param parent_id: ID of existing template the component is assigned to
    :return List of non-inherited (own) components
    """
    c_def = TEMPLATE_COMPONENT_DEF[component]
    q_params = dict(c_def["output"])
    q_params.update({c_def["qselectpid"]: parent_id})

    existing_clist_all = __salt__["zabbix.run_query"](
        c_def["qtype"] + ".get", q_params, **kwargs
    )

    # in some cases (e.g. templatescreens) the logic is reversed (even name of the flag is different!)
    if c_def["inherited"] == "inherited":
        q_params.update({c_def["inherited"]: "true"})
        existing_clist_inherited = __salt__["zabbix.run_query"](
            c_def["qtype"] + ".get", q_params, **kwargs
        )
    else:
        existing_clist_inherited = []

    if existing_clist_inherited:
        return [
            c_all
            for c_all in existing_clist_all
            if c_all not in existing_clist_inherited
        ]

    return existing_clist_all


def _adjust_object_lists(obj):
    """
    For creation or update of object that have attribute which contains a list Zabbix awaits plain list of IDs while
    querying Zabbix for same object returns list of dicts

    :param obj: Zabbix object parameters
    """
    for subcomp in TEMPLATE_COMPONENT_DEF:
        if subcomp in obj and TEMPLATE_COMPONENT_DEF[subcomp]["adjust"]:
            obj[subcomp] = [
                item[TEMPLATE_COMPONENT_DEF[subcomp]["qidname"]]
                for item in obj[subcomp]
            ]


def _manage_component(
    component, parent_id, defined, existing, template_id=None, **kwargs
):
    """
    Takes particular component list, compares it with existing, call appropriate API methods - create, update, delete.

    :param component: component name
    :param parent_id: ID of parent entity under which component should be created
    :param defined: list of defined items of named component
    :param existing: list of existing items of named component
    :param template_id: In case that component need also template ID for creation (although parent_id is given?!?!?)
    """
    zabbix_id_mapper = __salt__["zabbix.get_zabbix_id_mapper"]()

    dry_run = __opts__["test"]
    c_def = TEMPLATE_COMPONENT_DEF[component]
    compare_key = c_def["filter"]

    defined_set = {item[compare_key] for item in defined}
    existing_set = {item[compare_key] for item in existing}

    create_set = defined_set - existing_set
    update_set = defined_set & existing_set
    delete_set = existing_set - defined_set

    create_list = [item for item in defined if item[compare_key] in create_set]
    for object_params in create_list:
        if parent_id:
            object_params.update({c_def["pid_ref_name"]: parent_id})

        if "pid_ref_name2" in c_def:
            object_params.update({c_def["pid_ref_name2"]: template_id})

        _adjust_object_lists(object_params)

        if not dry_run:
            object_create = __salt__["zabbix.run_query"](
                c_def["qtype"] + ".create", object_params, **kwargs
            )
            if object_create:
                object_ids = object_create[c_def["res_id_name"]]
                CHANGE_STACK.append(
                    {
                        "component": component,
                        "action": "create",
                        "params": object_params,
                        c_def["filter"]: object_params[c_def["filter"]],
                        "object_id": object_ids,
                    }
                )
        else:
            CHANGE_STACK.append(
                {
                    "component": component,
                    "action": "create",
                    "params": object_params,
                    "object_id": "CREATED "
                    + TEMPLATE_COMPONENT_DEF[component]["qtype"]
                    + " ID",
                }
            )

    delete_list = [item for item in existing if item[compare_key] in delete_set]
    for object_del in delete_list:
        object_id_name = zabbix_id_mapper[c_def["qtype"]]
        CHANGE_STACK.append(
            {
                "component": component,
                "action": "delete",
                "params": [object_del[object_id_name]],
            }
        )
        if not dry_run:
            __salt__["zabbix.run_query"](
                c_def["qtype"] + ".delete", [object_del[object_id_name]], **kwargs
            )

    for object_name in update_set:
        ditem = next(
            (item for item in defined if item[compare_key] == object_name), None
        )
        eitem = next(
            (item for item in existing if item[compare_key] == object_name), None
        )
        diff_params = __salt__["zabbix.compare_params"](ditem, eitem, True)

        if diff_params["new"]:
            diff_params["new"][zabbix_id_mapper[c_def["qtype"]]] = eitem[
                zabbix_id_mapper[c_def["qtype"]]
            ]
            diff_params["old"][zabbix_id_mapper[c_def["qtype"]]] = eitem[
                zabbix_id_mapper[c_def["qtype"]]
            ]
            _adjust_object_lists(diff_params["new"])
            _adjust_object_lists(diff_params["old"])
            CHANGE_STACK.append(
                {
                    "component": component,
                    "action": "update",
                    "params": diff_params["new"],
                }
            )

            if not dry_run:
                __salt__["zabbix.run_query"](
                    c_def["qtype"] + ".update", diff_params["new"], **kwargs
                )


def is_present(name, **kwargs):
    """
    Check if Zabbix Template already exists.

    :param name: Zabbix Template name
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        does_zabbix-template-exist:
            zabbix_template.is_present:
                - name: Template OS Linux
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    try:
        object_id = __salt__["zabbix.get_object_id_by_params"](
            "template", {"filter": {"name": name}}, **kwargs
        )
    except SaltException:
        object_id = False

    if not object_id:
        ret["result"] = False
        ret["comment"] = f'Zabbix Template "{name}" does not exist.'
    else:
        ret["result"] = True
        ret["comment"] = f'Zabbix Template "{name}" exists.'

    return ret


# pylint: disable=too-many-statements,too-many-locals
def present(name, params, static_host_list=True, **kwargs):
    """
    Creates Zabbix Template object or if differs update it according defined parameters. See Zabbix API documentation.

    Zabbix API version: >3.0

    :param name: Zabbix Template name
    :param params: Additional parameters according to Zabbix API documentation
    :param static_host_list: If hosts assigned to the template are controlled
        only by this state or can be also assigned externally
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. note::

        If there is a need to get a value from current zabbix online (e.g. ids of host groups you want the template
        to be associated with), put a dictionary with two keys "query_object" and "query_name" instead of the value.
        In this example we want to create template named "Testing Template", assign it to hostgroup Templates,
        link it to two ceph nodes and create a macro.

    .. note::

        IMPORTANT NOTE:
        Objects (except for template name) are identified by name (or by other key in some exceptional cases)
        so changing name of object means deleting old one and creating new one with new ID !!!

    .. note::

        NOT SUPPORTED FEATURES:
            - linked templates
            - trigger dependencies
            - groups and group prototypes for host prototypes

    SLS Example:

    .. code-block:: yaml

        zabbix-template-present:
            zabbix_template.present:
                - name: Testing Template
                # Do not touch existing assigned hosts
                # True will detach all other hosts than defined here
                - static_host_list: False
                - params:
                    description: Template for Ceph nodes
                    groups:
                        # groups must already exist
                        # template must be at least in one hostgroup
                        - groupid:
                            query_object: hostgroup
                            query_name: Templates
                    macros:
                        - macro: "{$CEPH_CLUSTER_NAME}"
                          value: ceph
                    hosts:
                        # hosts must already exist
                        - hostid:
                            query_object: host
                            query_name: ceph-osd-01
                        - hostid:
                            query_object: host
                            query_name: ceph-osd-02
                    # templates:
                    # Linked templates - not supported by state module but can be linked manually (will not be touched)

                    applications:
                        - name: Ceph OSD
                    items:
                        - name: Ceph OSD avg fill item
                          key_: ceph.osd_avg_fill
                          type: 2
                          value_type: 0
                          delay: 60
                          units: '%'
                          description: 'Average fill of OSD'
                          applications:
                              - applicationid:
                                  query_object: application
                                  query_name: Ceph OSD
                    triggers:
                        - description: "Ceph OSD filled more that 90%"
                          expression: "{{'{'}}Testing Template:ceph.osd_avg_fill.last(){{'}'}}>90"
                          priority: 4
                    discoveries:
                        - name: Mounted filesystem discovery
                          key_: vfs.fs.discovery
                          type: 0
                          delay: 60
                          itemprototypes:
                              - name: Free disk space on {{'{#'}}FSNAME}
                                key_: vfs.fs.size[{{'{#'}}FSNAME},free]
                                type: 0
                                value_type: 3
                                delay: 60
                                applications:
                                    - applicationid:
                                        query_object: application
                                        query_name: Ceph OSD
                          triggerprototypes:
                              - description: "Free disk space is less than 20% on volume {{'{#'}}FSNAME{{'}'}}"
                                expression: "{{'{'}}Testing Template:vfs.fs.size[{{'{#'}}FSNAME},free].last(){{'}'}}<20"
                    graphs:
                        - name: Ceph OSD avg fill graph
                          width: 900
                          height: 200
                          graphtype: 0
                          gitems:
                              - color: F63100
                                itemid:
                                  query_object: item
                                  query_name: Ceph OSD avg fill item
                    screens:
                        - name: Ceph
                          hsize: 1
                          vsize: 1
                          screenitems:
                              - x: 0
                                y: 0
                                resourcetype: 0
                                resourceid:
                                    query_object: graph
                                    query_name: Ceph OSD avg fill graph
    """
    zabbix_id_mapper = __salt__["zabbix.get_zabbix_id_mapper"]()

    dry_run = __opts__["test"]
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    params["host"] = name

    del CHANGE_STACK[:]

    # Divide template yaml definition into parts
    # - template definition itself
    # - simple template components
    # - components that have other sub-components
    #   (e.g. discoveries - where parent ID is needed in advance for sub-component manipulation)
    template_definition = {}
    template_components = {}
    discovery_components = []

    for attr in params:
        if attr in TEMPLATE_COMPONENT_ORDER and str(attr) != "discoveries":
            template_components[attr] = params[attr]

        elif str(attr) == "discoveries":
            d_rules = []
            for d_rule in params[attr]:
                d_rule_components = {
                    "query_pid": {
                        "component": attr,
                        "filter_val": d_rule[TEMPLATE_COMPONENT_DEF[attr]["filter"]],
                    }
                }
                for proto_name in DISCOVERYRULE_COMPONENT_ORDER:
                    if proto_name in d_rule:
                        d_rule_components[proto_name] = d_rule[proto_name]
                        del d_rule[proto_name]

                discovery_components.append(d_rule_components)
                d_rules.append(d_rule)

            template_components[attr] = d_rules

        else:
            template_definition[attr] = params[attr]

    # if a component is not defined, it means to remove existing items during update (empty list)
    for attr in TEMPLATE_COMPONENT_ORDER:
        if attr not in template_components:
            template_components[attr] = []

    # if a component is not defined, it means to remove existing items during update (empty list)
    for attr in TEMPLATE_RELATIONS:
        template_definition[attr] = (
            params[attr] if attr in params and params[attr] else []
        )

    defined_obj = __salt__["zabbix.substitute_params"](template_definition, **kwargs)
    log.info(
        "SUBSTITUTED template_definition: %s",
        str(json.dumps(defined_obj, indent=4)),
    )

    tmpl_get = __salt__["zabbix.run_query"](
        "template.get",
        {
            "output": "extend",
            "selectGroups": "groupid",
            "selectHosts": "hostid",
            "selectTemplates": "templateid",
            "selectMacros": "extend",
            "filter": {"host": name},
        },
        **kwargs,
    )
    log.info("TEMPLATE get result: %s", str(json.dumps(tmpl_get, indent=4)))

    existing_obj = (
        __salt__["zabbix.substitute_params"](tmpl_get[0], **kwargs)
        if tmpl_get and len(tmpl_get) == 1
        else False
    )

    if existing_obj:
        template_id = existing_obj[zabbix_id_mapper["template"]]

        if not static_host_list:
            # Prepare objects for comparison
            defined_wo_hosts = defined_obj
            if "hosts" in defined_obj:
                defined_hosts = defined_obj["hosts"]
                del defined_wo_hosts["hosts"]
            else:
                defined_hosts = []

            existing_wo_hosts = existing_obj
            if "hosts" in existing_obj:
                existing_hosts = existing_obj["hosts"]
                del existing_wo_hosts["hosts"]
            else:
                existing_hosts = []

            # Compare host list separately from the rest of the object comparison since the merged list is needed for
            # update
            hosts_list = _diff_and_merge_host_list(defined_hosts, existing_hosts)

            # Compare objects without hosts
            diff_params = __salt__["zabbix.compare_params"](
                defined_wo_hosts, existing_wo_hosts, True
            )

            # Merge comparison results together
            if ("new" in diff_params and "hosts" in diff_params["new"]) or hosts_list:
                diff_params["new"]["hosts"] = hosts_list

        else:
            diff_params = __salt__["zabbix.compare_params"](
                defined_obj, existing_obj, True
            )

        if diff_params["new"]:
            diff_params["new"][zabbix_id_mapper["template"]] = template_id
            diff_params["old"][zabbix_id_mapper["template"]] = template_id
            log.info(
                "TEMPLATE: update params: %s",
                str(json.dumps(diff_params, indent=4)),
            )

            CHANGE_STACK.append(
                {
                    "component": "template",
                    "action": "update",
                    "params": diff_params["new"],
                }
            )
            if not dry_run:
                tmpl_update = __salt__["zabbix.run_query"](
                    "template.update", diff_params["new"], **kwargs
                )
                log.info("TEMPLATE update result: %s", str(tmpl_update))

    else:
        CHANGE_STACK.append(
            {"component": "template", "action": "create", "params": defined_obj}
        )
        if not dry_run:
            tmpl_create = __salt__["zabbix.run_query"](
                "template.create", defined_obj, **kwargs
            )
            log.info("TEMPLATE create result: %s", str(tmpl_create))
            if tmpl_create:
                template_id = tmpl_create["templateids"][0]

    log.info("\n\ntemplate_components: %s", json.dumps(template_components, indent=4))
    log.info("\n\ndiscovery_components: %s", json.dumps(discovery_components, indent=4))
    log.info(
        "\n\nCurrent CHANGE_STACK: %s",
        str(json.dumps(CHANGE_STACK, indent=4)),
    )

    if existing_obj or not dry_run:
        for component in TEMPLATE_COMPONENT_ORDER:
            log.info("\n\n\n\n\nCOMPONENT: %s\n\n", str(json.dumps(component)))
            # 1) query for components which belongs to the template
            existing_c_list = _get_existing_template_c_list(
                component, template_id, **kwargs
            )
            existing_c_list_subs = (
                __salt__["zabbix.substitute_params"](existing_c_list, **kwargs)
                if existing_c_list
                else []
            )

            if component in template_components:
                defined_c_list_subs = __salt__["zabbix.substitute_params"](
                    template_components[component],
                    extend_params={
                        TEMPLATE_COMPONENT_DEF[component]["qselectpid"]: template_id
                    },
                    filter_key=TEMPLATE_COMPONENT_DEF[component]["filter"],
                    **kwargs,
                )
            else:
                defined_c_list_subs = []
            # 2) take lists of particular component and compare -> do create, update and delete actions
            _manage_component(
                component,
                template_id,
                defined_c_list_subs,
                existing_c_list_subs,
                **kwargs,
            )

        log.info(
            "\n\nCurrent CHANGE_STACK: %s",
            str(json.dumps(CHANGE_STACK, indent=4)),
        )

        for d_rule_component in discovery_components:
            # query for parent id -> "query_pid": {"filter_val": "vfs.fs.discovery", "component": "discoveries"}
            q_def = d_rule_component["query_pid"]
            c_def = TEMPLATE_COMPONENT_DEF[q_def["component"]]
            q_object = c_def["qtype"]
            q_params = dict(c_def["output"])
            q_params.update({c_def["qselectpid"]: template_id})
            q_params.update({"filter": {c_def["filter"]: q_def["filter_val"]}})

            parent_id = __salt__["zabbix.get_object_id_by_params"](
                q_object, q_params, **kwargs
            )

            for proto_name in DISCOVERYRULE_COMPONENT_ORDER:
                log.info(
                    "\n\n\n\n\nPROTOTYPE_NAME: %s\n\n",
                    str(json.dumps(proto_name)),
                )
                existing_p_list = _get_existing_template_c_list(
                    proto_name, parent_id, **kwargs
                )
                existing_p_list_subs = (
                    __salt__["zabbix.substitute_params"](existing_p_list, **kwargs)
                    if existing_p_list
                    else []
                )

                if proto_name in d_rule_component:
                    defined_p_list_subs = __salt__["zabbix.substitute_params"](
                        d_rule_component[proto_name],
                        extend_params={c_def["qselectpid"]: template_id},
                        **kwargs,
                    )
                else:
                    defined_p_list_subs = []

                _manage_component(
                    proto_name,
                    parent_id,
                    defined_p_list_subs,
                    existing_p_list_subs,
                    template_id=template_id,
                    **kwargs,
                )

    log.info(
        "\n\nCurrent CHANGE_STACK: %s",
        str(json.dumps(CHANGE_STACK, indent=4)),
    )

    if not CHANGE_STACK:
        ret["result"] = True
        ret["comment"] = (
            'Zabbix Template "{}" already exists and corresponds to a definition.'.format(
                name
            )
        )
    else:
        tmpl_action = next(
            (
                item
                for item in CHANGE_STACK
                if item["component"] == "template" and item["action"] == "create"
            ),
            None,
        )
        if tmpl_action:
            ret["result"] = True
            if dry_run:
                ret["comment"] = f'Zabbix Template "{name}" would be created.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Template "{name}" does not exist.',
                        "new": (
                            'Zabbix Template "{}" would be created '
                            "according definition.".format(name)
                        ),
                    }
                }
            else:
                ret["comment"] = f'Zabbix Template "{name}" created.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Template "{name}" did not exist.',
                        "new": (
                            'Zabbix Template "{}" created according definition.'.format(
                                name
                            )
                        ),
                    }
                }
        else:
            ret["result"] = True
            if dry_run:
                ret["comment"] = f'Zabbix Template "{name}" would be updated.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Template "{name}" differs.',
                        "new": (
                            'Zabbix Template "{}" would be updated '
                            "according definition.".format(name)
                        ),
                    }
                }
            else:
                ret["comment"] = f'Zabbix Template "{name}" updated.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Template "{name}" differed.',
                        "new": (
                            'Zabbix Template "{}" updated according definition.'.format(
                                name
                            )
                        ),
                    }
                }

    return ret


def absent(name, **kwargs):
    """
    Makes the Zabbix Template to be absent (either does not exist or delete it).

    :param name: Zabbix Template name
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        zabbix-template-absent:
            zabbix_template.absent:
                - name: Ceph OSD
    """
    dry_run = __opts__["test"]
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    try:
        object_id = __salt__["zabbix.get_object_id_by_params"](
            "template", {"filter": {"name": name}}, **kwargs
        )
    except SaltException:
        object_id = False

    if not object_id:
        ret["result"] = True
        ret["comment"] = f'Zabbix Template "{name}" does not exist.'
    else:
        if dry_run:
            ret["result"] = True
            ret["comment"] = f'Zabbix Template "{name}" would be deleted.'
            ret["changes"] = {
                name: {
                    "old": f'Zabbix Template "{name}" exists.',
                    "new": f'Zabbix Template "{name}" would be deleted.',
                }
            }
        else:
            tmpl_delete = __salt__["zabbix.run_query"](
                "template.delete", [object_id], **kwargs
            )
            if tmpl_delete:
                ret["result"] = True
                ret["comment"] = f'Zabbix Template "{name}" deleted.'
                ret["changes"] = {
                    name: {
                        "old": f'Zabbix Template "{name}" existed.',
                        "new": f'Zabbix Template "{name}" deleted.',
                    }
                }

    return ret
