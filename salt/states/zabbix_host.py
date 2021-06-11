"""
Management of Zabbix hosts.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>


"""

from copy import deepcopy

import salt.utils.json


def __virtual__():
    """
    Only make these states available if Zabbix module is available.
    """
    if "zabbix.host_create" in __salt__:
        return True
    return (False, "zabbix module could not be loaded")


def present(host, groups, interfaces, **kwargs):
    """
    Ensures that the host exists, eventually creates new host.
    NOTE: please use argument visible_name instead of name to not mess with name from salt sls. This function accepts
    all standard host properties: keyword argument names differ depending on your zabbix version, see:
    https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host

    .. versionadded:: 2016.3.0

    :param host: technical name of the host
    :param groups: groupids of host groups to add the host to
    :param interfaces: interfaces to be created for the host
    :param proxy_host: Optional proxy name or proxyid to monitor host
    :param inventory: Optional list of inventory names and values
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)
    :param visible_name: Optional - string with visible name of the host, use 'visible_name' instead of 'name' \
    parameter to not mess with value supplied from Salt sls file.

    .. code-block:: yaml

        create_test_host:
            zabbix_host.present:
                - host: TestHostWithInterfaces
                - proxy_host: 12345
                - groups:
                    - 5
                    - 6
                    - 7
                - interfaces:
                    - test1.example.com:
                        - ip: '192.168.1.8'
                        - type: 'Agent'
                        - port: 92
                    - testing2_create:
                        - ip: '192.168.1.9'
                        - dns: 'test2.example.com'
                        - type: 'agent'
                        - main: false
                    - testovaci1_ipmi:
                        - ip: '192.168.100.111'
                        - type: 'ipmi'
                - inventory:
                    - alias: some alias
                    - asset_tag: jlm3937


    """
    connection_args = {}
    if "_connection_user" in kwargs:
        connection_args["_connection_user"] = kwargs.pop("_connection_user")
    if "_connection_password" in kwargs:
        connection_args["_connection_password"] = kwargs.pop("_connection_password")
    if "_connection_url" in kwargs:
        connection_args["_connection_url"] = kwargs.pop("_connection_url")

    ret = {"name": host, "changes": {}, "result": False, "comment": ""}

    # Comment and change messages
    comment_host_created = "Host {} created.".format(host)
    comment_host_updated = "Host {} updated.".format(host)
    comment_host_notcreated = "Unable to create host: {}. ".format(host)
    comment_host_exists = "Host {} already exists.".format(host)
    changes_host_created = {
        host: {
            "old": "Host {} does not exist.".format(host),
            "new": "Host {} created.".format(host),
        }
    }

    def _interface_format(interfaces_data):
        """
        Formats interfaces from SLS file into valid JSON usable for zabbix API.
        Completes JSON with default values.

        :param interfaces_data: list of interfaces data from SLS file

        """

        if not interfaces_data:
            return list()

        interface_attrs = ("ip", "dns", "main", "type", "useip", "port", "details")
        interfaces_json = salt.utils.json.loads(salt.utils.json.dumps(interfaces_data))
        interfaces_dict = dict()

        for interface in interfaces_json:
            for intf in interface:
                intf_name = intf
                interfaces_dict[intf_name] = dict()
                for intf_val in interface[intf]:
                    for key, value in intf_val.items():
                        if key in interface_attrs:
                            interfaces_dict[intf_name][key] = value

        interfaces_list = list()
        interface_ports = {
            "agent": ["1", "10050"],
            "snmp": ["2", "161"],
            "ipmi": ["3", "623"],
            "jmx": ["4", "12345"],
        }

        for key, value in interfaces_dict.items():
            # Load interface values or default values
            interface_type = interface_ports[value["type"].lower()][0]
            main = "1" if str(value.get("main", "true")).lower() == "true" else "0"
            useip = "1" if str(value.get("useip", "true")).lower() == "true" else "0"
            interface_ip = value.get("ip", "")
            dns = value.get("dns", key)
            port = str(value.get("port", interface_ports[value["type"].lower()][1]))
            if interface_type == "2":
                if not value.get("details", False):
                    details_version = "2"
                    details_bulk = "1"
                    details_community = "{$SNMP_COMMUNITY}"
                else:
                    val_details = {}
                    for detail in value.get("details"):
                        val_details.update(detail)
                    details_version = val_details.get("version", "2")
                    details_bulk = val_details.get("bulk", "1")
                    details_community = val_details.get(
                        "community", "{$SNMP_COMMUNITY}"
                    )
                details = {
                    "version": details_version,
                    "bulk": details_bulk,
                    "community": details_community,
                }
                if details_version == "3":
                    details_securitylevel = val_details.get("securitylevel", "0")
                    details_securityname = val_details.get("securityname", "")
                    details_contextname = val_details.get("contextname", "")
                    details["securitylevel"] = details_securitylevel
                    details["securityname"] = details_securityname
                    details["contextname"] = details_contextname
                    if int(details_securitylevel) > 0:
                        details_authpassphrase = val_details.get("authpassphrase", "")
                        details_authprotocol = val_details.get("authprotocol", "0")
                        details["authpassphrase"] = details_authpassphrase
                        details["authprotocol"] = details_authprotocol
                        if int(details_securitylevel) > 1:
                            details_privpassphrase = val_details.get(
                                "privpassphrase", ""
                            )
                            details_privprotocol = val_details.get("privprotocol", "0")
                            details["privpassphrase"] = details_privpassphrase
                            details["privprotocol"] = details_privprotocol
            else:
                details = []

            interfaces_list.append(
                {
                    "type": interface_type,
                    "main": main,
                    "useip": useip,
                    "ip": interface_ip,
                    "dns": dns,
                    "port": port,
                    "details": details,
                }
            )

        interfaces_list_sorted = sorted(
            interfaces_list, key=lambda k: k["main"], reverse=True
        )

        return interfaces_list_sorted

    interfaces_formated = _interface_format(interfaces)

    # Ensure groups are all groupid
    groupids = []
    for group in groups:
        if isinstance(group, str):
            groupid = __salt__["zabbix.hostgroup_get"](name=group, **connection_args)
            try:
                groupids.append(int(groupid[0]["groupid"]))
            except TypeError:
                ret["comment"] = "Invalid group {}".format(group)
                return ret
        else:
            groupids.append(group)
    groups = groupids

    # Get and validate proxyid
    proxy_hostid = "0"
    if "proxy_host" in kwargs:
        proxy_host = kwargs.pop("proxy_host")
        # Test if proxy_host given as name
        if isinstance(proxy_host, str):
            try:
                proxy_hostid = __salt__["zabbix.run_query"](
                    "proxy.get",
                    {
                        "output": "proxyid",
                        "selectInterface": "extend",
                        "filter": {"host": "{}".format(proxy_host)},
                    },
                    **connection_args
                )[0]["proxyid"]
            except TypeError:
                ret["comment"] = "Invalid proxy_host {}".format(proxy_host)
                return ret
        # Otherwise lookup proxy_host as proxyid
        else:
            try:
                proxy_hostid = __salt__["zabbix.run_query"](
                    "proxy.get",
                    {"proxyids": "{}".format(proxy_host), "output": "proxyid"},
                    **connection_args
                )[0]["proxyid"]
            except TypeError:
                ret["comment"] = "Invalid proxy_host {}".format(proxy_host)
                return ret

    inventory = kwargs.pop("inventory", None)
    if inventory is None:
        inventory = {}
    # Create dict of requested inventory items
    new_inventory = {}
    for inv_item in inventory:
        for k, v in inv_item.items():
            new_inventory[k] = str(v)

    visible_name = kwargs.pop("visible_name", None)

    host_extra_properties = {}
    if kwargs:
        host_properties_definition = [
            "description",
            "inventory_mode",
            "ipmi_authtype",
            "ipmi_password",
            "ipmi_privilege",
            "ipmi_username",
            "status",
            "tls_connect",
            "tls_accept",
            "tls_issuer",
            "tls_subject",
            "tls_psk_identity",
            "tls_psk",
        ]
        for param in host_properties_definition:
            if param in kwargs:
                host_extra_properties[param] = kwargs.pop(param)

    host_exists = __salt__["zabbix.host_exists"](host, **connection_args)

    if host_exists:
        host = __salt__["zabbix.host_get"](host=host, **connection_args)[0]
        hostid = host["hostid"]

        update_host = False
        update_proxy = False
        update_hostgroups = False
        update_interfaces = False
        update_inventory = False

        host_updated_params = {}
        for param in host_extra_properties:
            if param in host:
                if host[param] == host_extra_properties[param]:
                    continue
            host_updated_params[param] = host_extra_properties[param]
        if host_updated_params:
            update_host = True

        cur_proxy_hostid = host["proxy_hostid"]
        if proxy_hostid != cur_proxy_hostid:
            update_proxy = True

        hostgroups = __salt__["zabbix.hostgroup_get"](hostids=hostid, **connection_args)
        cur_hostgroups = list()

        for hostgroup in hostgroups:
            cur_hostgroups.append(int(hostgroup["groupid"]))

        if set(groups) != set(cur_hostgroups):
            update_hostgroups = True

        hostinterfaces = __salt__["zabbix.hostinterface_get"](
            hostids=hostid, **connection_args
        )

        if hostinterfaces:
            hostinterfaces = sorted(hostinterfaces, key=lambda k: k["main"])
            hostinterfaces_copy = deepcopy(hostinterfaces)
            for hostintf in hostinterfaces_copy:
                hostintf.pop("interfaceid")
                hostintf.pop("hostid")
                # "bulk" is present only in snmp interfaces with Zabbix < 5.0
                if "bulk" in hostintf:
                    hostintf.pop("bulk")
                    # as we always sent the "details" it needs to be
                    # populated in Zabbix < 5.0 response:
                    if hostintf["type"] == "2":
                        hostintf["details"] = {
                            "version": "2",
                            "bulk": "1",
                            "community": "{$SNMP_COMMUNITY}",
                        }
                    else:
                        hostintf["details"] = []
            interface_diff = [
                x for x in interfaces_formated if x not in hostinterfaces_copy
            ] + [y for y in hostinterfaces_copy if y not in interfaces_formated]
            if interface_diff:
                update_interfaces = True

        elif not hostinterfaces and interfaces:
            update_interfaces = True

        cur_inventory = __salt__["zabbix.host_inventory_get"](
            hostids=hostid, **connection_args
        )
        if cur_inventory:
            # Remove blank inventory items
            cur_inventory = {k: v for k, v in cur_inventory.items() if v}
            # Remove persistent inventory keys for comparison
            cur_inventory.pop("hostid", None)
            cur_inventory.pop("inventory_mode", None)

        if not cur_inventory:
            if new_inventory:
                update_inventory = True
        elif set(cur_inventory) != set(new_inventory):
            update_inventory = True

    # Dry run, test=true mode
    if __opts__["test"]:
        if host_exists:
            if (
                update_host
                or update_hostgroups
                or update_interfaces
                or update_proxy
                or update_inventory
            ):
                ret["result"] = None
                ret["comment"] = comment_host_updated
            else:
                ret["result"] = True
                ret["comment"] = comment_host_exists
        else:
            ret["result"] = None
            ret["comment"] = comment_host_created
            ret["changes"] = changes_host_created
        return ret

    error = []

    if host_exists:
        ret["result"] = True
        if (
            update_host
            or update_hostgroups
            or update_interfaces
            or update_proxy
            or update_inventory
        ):

            if update_host:
                # combine connection_args and host_updated_params
                sum_kwargs = deepcopy(host_updated_params)
                sum_kwargs.update(connection_args)
                hostupdate = __salt__["zabbix.host_update"](hostid, **sum_kwargs)
                ret["changes"]["host"] = str(host_updated_params)
                if "error" in hostupdate:
                    error.append(hostupdate["error"])
            if update_inventory:
                # combine connection_args, inventory, and clear_old
                sum_kwargs = dict(new_inventory)
                sum_kwargs.update(connection_args)
                sum_kwargs["clear_old"] = True

                hostupdate = __salt__["zabbix.host_inventory_set"](hostid, **sum_kwargs)
                ret["changes"]["inventory"] = str(new_inventory)
                if "error" in hostupdate:
                    error.append(hostupdate["error"])
            if update_proxy:
                hostupdate = __salt__["zabbix.host_update"](
                    hostid, proxy_hostid=proxy_hostid, **connection_args
                )
                ret["changes"]["proxy_hostid"] = str(proxy_hostid)
                if "error" in hostupdate:
                    error.append(hostupdate["error"])
            if update_hostgroups:
                hostupdate = __salt__["zabbix.host_update"](
                    hostid, groups=groups, **connection_args
                )
                ret["changes"]["groups"] = str(groups)
                if "error" in hostupdate:
                    error.append(hostupdate["error"])
            if update_interfaces:
                interfaceid_by_type = {
                    "1": [],  # agent
                    "2": [],  # snmp
                    "3": [],  # ipmi
                    "4": [],  # jmx
                }
                other_interfaces = []

                if hostinterfaces:
                    for interface in hostinterfaces:
                        if interface["main"]:
                            interfaceid_by_type[interface["type"]].insert(
                                0, interface["interfaceid"]
                            )
                        else:
                            interfaceid_by_type[interface["type"]].append(
                                interface["interfaceid"]
                            )

                def _update_interfaces(interface):
                    if not interfaceid_by_type[interface["type"]]:
                        ret = __salt__["zabbix.hostinterface_create"](
                            hostid,
                            interface["ip"],
                            dns=interface["dns"],
                            main=interface["main"],
                            if_type=interface["type"],
                            useip=interface["useip"],
                            port=interface["port"],
                            details=interface["details"],
                            **connection_args
                        )
                    else:
                        interfaceid = interfaceid_by_type[interface["type"]].pop(0)
                        ret = __salt__["zabbix.hostinterface_update"](
                            interfaceid=interfaceid,
                            ip=interface["ip"],
                            dns=interface["dns"],
                            main=interface["main"],
                            type=interface["type"],
                            useip=interface["useip"],
                            port=interface["port"],
                            details=interface["details"],
                            **connection_args
                        )
                    return ret

                # First we try to update the "default" interfaces every host
                # needs at least one "default" interface
                for interface in interfaces_formated:
                    if interface["main"]:
                        updatedint = _update_interfaces(interface)
                        if "error" in updatedint:
                            error.append(updatedint["error"])
                    else:
                        other_interfaces.append(interface)

                # Second we update the other interfaces
                for interface in other_interfaces:
                    updatedint = _update_interfaces(interface)
                    if "error" in updatedint:
                        error.append(updatedint["error"])

                # And finally remove the ones that isn't in the host state
                for interface_type in interfaceid_by_type:
                    for interfaceid in interfaceid_by_type[interface_type]:
                        __salt__["zabbix.hostinterface_delete"](
                            interfaceids=interfaceid, **connection_args
                        )

                ret["changes"]["interfaces"] = str(interfaces_formated)

            ret["comment"] = comment_host_updated

        else:
            ret["comment"] = comment_host_exists
    else:
        # combine connection_args and host_properties
        sum_kwargs = host_extra_properties
        sum_kwargs.update(connection_args)
        host_create = __salt__["zabbix.host_create"](
            host,
            groups,
            interfaces_formated,
            proxy_hostid=proxy_hostid,
            inventory=new_inventory,
            visible_name=visible_name,
            **sum_kwargs
        )

        if "error" not in host_create:
            ret["result"] = True
            ret["comment"] = comment_host_created
            ret["changes"] = changes_host_created
        else:
            ret["result"] = False
            ret["comment"] = comment_host_notcreated + str(host_create["error"])

    # error detected
    if error:
        ret["changes"] = {}
        ret["result"] = False
        ret["comment"] = str(error)

    return ret


def absent(name, **kwargs):
    """
    Ensures that the host does not exists, eventually deletes host.

    .. versionadded:: 2016.3.0

    :param: name: technical name of the host
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        TestHostWithInterfaces:
            zabbix_host.absent

    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Comment and change messages
    comment_host_deleted = "Host {} deleted.".format(name)
    comment_host_notdeleted = "Unable to delete host: {}. ".format(name)
    comment_host_notexists = "Host {} does not exist.".format(name)
    changes_host_deleted = {
        name: {
            "old": "Host {} exists.".format(name),
            "new": "Host {} deleted.".format(name),
        }
    }
    connection_args = {}
    if "_connection_user" in kwargs:
        connection_args["_connection_user"] = kwargs["_connection_user"]
    if "_connection_password" in kwargs:
        connection_args["_connection_password"] = kwargs["_connection_password"]
    if "_connection_url" in kwargs:
        connection_args["_connection_url"] = kwargs["_connection_url"]

    host_exists = __salt__["zabbix.host_exists"](name, **connection_args)

    # Dry run, test=true mode
    if __opts__["test"]:
        if not host_exists:
            ret["result"] = True
            ret["comment"] = comment_host_notexists
        else:
            ret["result"] = None
            ret["comment"] = comment_host_deleted
        return ret

    host_get = __salt__["zabbix.host_get"](name, **connection_args)

    if not host_get:
        ret["result"] = True
        ret["comment"] = comment_host_notexists
    else:
        try:
            hostid = host_get[0]["hostid"]
            host_delete = __salt__["zabbix.host_delete"](hostid, **connection_args)
        except KeyError:
            host_delete = False

        if host_delete and "error" not in host_delete:
            ret["result"] = True
            ret["comment"] = comment_host_deleted
            ret["changes"] = changes_host_deleted
        else:
            ret["result"] = False
            ret["comment"] = comment_host_notdeleted + str(host_delete["error"])

    return ret


def assign_templates(host, templates, **kwargs):
    """
    Ensures that templates are assigned to the host.

    .. versionadded:: 2017.7.0

    :param host: technical name of the host
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        add_zabbix_templates_to_host:
            zabbix_host.assign_templates:
                - host: TestHost
                - templates:
                    - "Template OS Linux"
                    - "Template App MySQL"

    """
    connection_args = {}
    if "_connection_user" in kwargs:
        connection_args["_connection_user"] = kwargs["_connection_user"]
    if "_connection_password" in kwargs:
        connection_args["_connection_password"] = kwargs["_connection_password"]
    if "_connection_url" in kwargs:
        connection_args["_connection_url"] = kwargs["_connection_url"]

    ret = {"name": host, "changes": {}, "result": False, "comment": ""}

    # Set comments
    comment_host_templates_updated = "Templates updated."
    comment_host_templ_notupdated = "Unable to update templates on host: {}.".format(
        host
    )
    comment_host_templates_in_sync = "Templates already synced."

    update_host_templates = False
    curr_template_ids = list()
    requested_template_ids = list()
    hostid = ""

    host_exists = __salt__["zabbix.host_exists"](host, **connection_args)

    # Fail out if host does not exist
    if not host_exists:
        ret["result"] = False
        ret["comment"] = comment_host_templ_notupdated
        return ret

    host_info = __salt__["zabbix.host_get"](host=host, **connection_args)[0]
    hostid = host_info["hostid"]

    if not templates:
        templates = list()

    # Get current templateids for host
    host_templates = __salt__["zabbix.host_get"](
        hostids=hostid,
        output='[{"hostid"}]',
        selectParentTemplates='["templateid"]',
        **connection_args
    )
    for template_id in host_templates[0]["parentTemplates"]:
        curr_template_ids.append(template_id["templateid"])

    # Get requested templateids
    for template in templates:
        try:
            template_id = __salt__["zabbix.template_get"](
                host=template, **connection_args
            )[0]["templateid"]
            requested_template_ids.append(template_id)
        except TypeError:
            ret["result"] = False
            ret["comment"] = "Unable to find template: {}.".format(template)
            return ret

    # remove any duplications
    requested_template_ids = list(set(requested_template_ids))

    if set(curr_template_ids) != set(requested_template_ids):
        update_host_templates = True

    # Set change output
    changes_host_templates_modified = {
        host: {
            "old": "Host templates: " + ", ".join(curr_template_ids),
            "new": "Host templates: " + ", ".join(requested_template_ids),
        }
    }

    # Dry run, test=true mode
    if __opts__["test"]:
        if update_host_templates:
            ret["result"] = None
            ret["comment"] = comment_host_templates_updated
        else:
            ret["result"] = True
            ret["comment"] = comment_host_templates_in_sync
        return ret

    # Attempt to perform update
    ret["result"] = True
    if update_host_templates:
        update_output = __salt__["zabbix.host_update"](
            hostid, templates=(requested_template_ids), **connection_args
        )
        if update_output is False:
            ret["result"] = False
            ret["comment"] = comment_host_templ_notupdated
            return ret
        ret["comment"] = comment_host_templates_updated
        ret["changes"] = changes_host_templates_modified
    else:
        ret["comment"] = comment_host_templates_in_sync

    return ret
