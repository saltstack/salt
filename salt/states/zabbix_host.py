# -*- coding: utf-8 -*-
'''
Management of Zabbix hosts.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>


'''
from __future__ import absolute_import, print_function, unicode_literals
from copy import deepcopy
from salt.ext import six
import salt.utils.json


def __virtual__():
    '''
    Only make these states available if Zabbix module is available.
    '''
    return 'zabbix.host_create' in __salt__


def present(host, groups, interfaces, **kwargs):
    '''
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


    '''
    connection_args = {}
    if '_connection_user' in kwargs:
        connection_args['_connection_user'] = kwargs['_connection_user']
    if '_connection_password' in kwargs:
        connection_args['_connection_password'] = kwargs['_connection_password']
    if '_connection_url' in kwargs:
        connection_args['_connection_url'] = kwargs['_connection_url']

    ret = {'name': host, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_host_created = 'Host {0} created.'.format(host)
    comment_host_updated = 'Host {0} updated.'.format(host)
    comment_host_notcreated = 'Unable to create host: {0}. '.format(host)
    comment_host_exists = 'Host {0} already exists.'.format(host)
    changes_host_created = {host: {'old': 'Host {0} does not exist.'.format(host),
                                   'new': 'Host {0} created.'.format(host),
                                   }
                            }

    def _interface_format(interfaces_data):
        '''
        Formats interfaces from SLS file into valid JSON usable for zabbix API.
        Completes JSON with default values.

        :param interfaces_data: list of interfaces data from SLS file

        '''

        if not interfaces_data:
            return list()

        interface_attrs = ('ip', 'dns', 'main', 'type', 'useip', 'port')
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
        interface_ports = {'agent': ['1', '10050'], 'snmp': ['2', '161'], 'ipmi': ['3', '623'],
                           'jmx': ['4', '12345']}

        for key, value in interfaces_dict.items():
            # Load interface values or default values
            interface_type = interface_ports[value['type'].lower()][0]
            main = '1' if six.text_type(value.get('main', 'true')).lower() == 'true' else '0'
            useip = '1' if six.text_type(value.get('useip', 'true')).lower() == 'true' else '0'
            interface_ip = value.get('ip', '')
            dns = value.get('dns', key)
            port = six.text_type(value.get('port', interface_ports[value['type'].lower()][1]))

            interfaces_list.append({'type': interface_type,
                                    'main': main,
                                    'useip': useip,
                                    'ip': interface_ip,
                                    'dns': dns,
                                    'port': port})

        interfaces_list_sorted = sorted(interfaces_list, key=lambda k: k['main'], reverse=True)

        return interfaces_list_sorted

    interfaces_formated = _interface_format(interfaces)

    # Ensure groups are all groupid
    groupids = []
    for group in groups:
        if isinstance(group, six.string_types):
            groupid = __salt__['zabbix.hostgroup_get'](name=group, **connection_args)
            try:
                groupids.append(int(groupid[0]['groupid']))
            except TypeError:
                ret['comment'] = 'Invalid group {0}'.format(group)
                return ret
        else:
            groupids.append(group)
    groups = groupids

    # Get and validate proxyid
    proxy_hostid = "0"
    if 'proxy_host' in kwargs:
        # Test if proxy_host given as name
        if isinstance(kwargs['proxy_host'], six.string_types):
            try:
                proxy_hostid = __salt__['zabbix.run_query']('proxy.get', {"output": "proxyid",
                                                            "selectInterface": "extend",
                                                            "filter": {"host": "{0}".format(kwargs['proxy_host'])}},
                                                            **connection_args)[0]['proxyid']
            except TypeError:
                ret['comment'] = 'Invalid proxy_host {0}'.format(kwargs['proxy_host'])
                return ret
        # Otherwise lookup proxy_host as proxyid
        else:
            try:
                proxy_hostid = __salt__['zabbix.run_query']('proxy.get', {"proxyids":
                                                            "{0}".format(kwargs['proxy_host']),
                                                            "output": "proxyid"},
                                                            **connection_args)[0]['proxyid']
            except TypeError:
                ret['comment'] = 'Invalid proxy_host {0}'.format(kwargs['proxy_host'])
                return ret

    if 'inventory' not in kwargs:
        inventory = {}
    else:
        inventory = kwargs['inventory']
    if inventory is None:
        inventory = {}
    # Create dict of requested inventory items
    new_inventory = {}
    for inv_item in inventory:
        for k, v in inv_item.items():
            new_inventory[k] = str(v)

    host_exists = __salt__['zabbix.host_exists'](host, **connection_args)

    if host_exists:
        host = __salt__['zabbix.host_get'](host=host, **connection_args)[0]
        hostid = host['hostid']

        update_proxy = False
        update_hostgroups = False
        update_interfaces = False
        update_inventory = False

        cur_proxy_hostid = host['proxy_hostid']
        if proxy_hostid != cur_proxy_hostid:
            update_proxy = True

        hostgroups = __salt__['zabbix.hostgroup_get'](hostids=hostid, **connection_args)
        cur_hostgroups = list()

        for hostgroup in hostgroups:
            cur_hostgroups.append(int(hostgroup['groupid']))

        if set(groups) != set(cur_hostgroups):
            update_hostgroups = True

        hostinterfaces = __salt__['zabbix.hostinterface_get'](hostids=hostid, **connection_args)

        if hostinterfaces:
            hostinterfaces = sorted(hostinterfaces, key=lambda k: k['main'])
            hostinterfaces_copy = deepcopy(hostinterfaces)
            for hostintf in hostinterfaces_copy:
                hostintf.pop('interfaceid')
                hostintf.pop('bulk')
                hostintf.pop('hostid')
            interface_diff = [x for x in interfaces_formated if x not in hostinterfaces_copy] + \
                             [y for y in hostinterfaces_copy if y not in interfaces_formated]
            if interface_diff:
                update_interfaces = True

        elif not hostinterfaces and interfaces:
            update_interfaces = True

        cur_inventory = __salt__['zabbix.host_inventory_get'](hostids=hostid, **connection_args)
        if cur_inventory:
            # Remove blank inventory items
            cur_inventory = {k: v for k, v in cur_inventory.items() if v}
            # Remove persistent inventory keys for comparison
            cur_inventory.pop('hostid', None)
            cur_inventory.pop('inventory_mode', None)

        if new_inventory and not cur_inventory:
            update_inventory = True
        elif set(cur_inventory) != set(new_inventory):
            update_inventory = True

    # Dry run, test=true mode
    if __opts__['test']:
        if host_exists:
            if update_hostgroups or update_interfaces or update_proxy or update_inventory:
                ret['result'] = None
                ret['comment'] = comment_host_updated
            else:
                ret['result'] = True
                ret['comment'] = comment_host_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_host_created
            ret['changes'] = changes_host_created
        return ret

    error = []

    if host_exists:
        ret['result'] = True
        if update_hostgroups or update_interfaces or update_proxy or update_inventory:

            if update_inventory:
                # combine connection_args, inventory, and clear_old
                sum_kwargs = dict(new_inventory)
                sum_kwargs.update(connection_args)
                sum_kwargs['clear_old'] = True

                hostupdate = __salt__['zabbix.host_inventory_set'](hostid, **sum_kwargs)
                ret['changes']['inventory'] = str(new_inventory)
                if 'error' in hostupdate:
                    error.append(hostupdate['error'])
            if update_proxy:
                hostupdate = __salt__['zabbix.host_update'](hostid, proxy_hostid=proxy_hostid, **connection_args)
                ret['changes']['proxy_hostid'] = six.text_type(proxy_hostid)
                if 'error' in hostupdate:
                    error.append(hostupdate['error'])
            if update_hostgroups:
                hostupdate = __salt__['zabbix.host_update'](hostid, groups=groups, **connection_args)
                ret['changes']['groups'] = six.text_type(groups)
                if 'error' in hostupdate:
                    error.append(hostupdate['error'])
            if update_interfaces:
                if hostinterfaces:
                    for interface in hostinterfaces:
                        __salt__['zabbix.hostinterface_delete'](interfaceids=interface['interfaceid'],
                                                                **connection_args)

                hostid = __salt__['zabbix.host_get'](name=host, **connection_args)[0]['hostid']

                for interface in interfaces_formated:
                    updatedint = __salt__['zabbix.hostinterface_create'](hostid=hostid,
                                                                         ip=interface['ip'],
                                                                         dns=interface['dns'],
                                                                         main=interface['main'],
                                                                         type=interface['type'],
                                                                         useip=interface['useip'],
                                                                         port=interface['port'],
                                                                         **connection_args)

                    if 'error' in updatedint:
                        error.append(updatedint['error'])

                ret['changes']['interfaces'] = six.text_type(interfaces_formated)

            ret['comment'] = comment_host_updated

        else:
            ret['comment'] = comment_host_exists
    else:
        host_create = __salt__['zabbix.host_create'](host,
                                                     groups,
                                                     interfaces_formated,
                                                     proxy_hostid=proxy_hostid,
                                                     inventory=new_inventory,
                                                     **connection_args)

        if 'error' not in host_create:
            ret['result'] = True
            ret['comment'] = comment_host_created
            ret['changes'] = changes_host_created
        else:
            ret['result'] = False
            ret['comment'] = comment_host_notcreated + six.text_type(host_create['error'])

    # error detected
    if error:
        ret['changes'] = {}
        ret['result'] = False
        ret['comment'] = six.text_type(error)

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
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_host_deleted = 'Host {0} deleted.'.format(name)
    comment_host_notdeleted = 'Unable to delete host: {0}. '.format(name)
    comment_host_notexists = 'Host {0} does not exist.'.format(name)
    changes_host_deleted = {name: {'old': 'Host {0} exists.'.format(name),
                                   'new': 'Host {0} deleted.'.format(name),
                                   }
                            }
    connection_args = {}
    if '_connection_user' in kwargs:
        connection_args['_connection_user'] = kwargs['_connection_user']
    if '_connection_password' in kwargs:
        connection_args['_connection_password'] = kwargs['_connection_password']
    if '_connection_url' in kwargs:
        connection_args['_connection_url'] = kwargs['_connection_url']

    host_exists = __salt__['zabbix.host_exists'](name, **connection_args)

    # Dry run, test=true mode
    if __opts__['test']:
        if not host_exists:
            ret['result'] = True
            ret['comment'] = comment_host_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_host_deleted
        return ret

    host_get = __salt__['zabbix.host_get'](name, **connection_args)

    if not host_get:
        ret['result'] = True
        ret['comment'] = comment_host_notexists
    else:
        try:
            hostid = host_get[0]['hostid']
            host_delete = __salt__['zabbix.host_delete'](hostid, **connection_args)
        except KeyError:
            host_delete = False

        if host_delete and 'error' not in host_delete:
            ret['result'] = True
            ret['comment'] = comment_host_deleted
            ret['changes'] = changes_host_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_host_notdeleted + six.text_type(host_delete['error'])

    return ret


def assign_templates(host, templates, **kwargs):
    '''
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

    '''
    connection_args = {}
    if '_connection_user' in kwargs:
        connection_args['_connection_user'] = kwargs['_connection_user']
    if '_connection_password' in kwargs:
        connection_args['_connection_password'] = kwargs['_connection_password']
    if '_connection_url' in kwargs:
        connection_args['_connection_url'] = kwargs['_connection_url']

    ret = {'name': host, 'changes': {}, 'result': False, 'comment': ''}

    # Set comments
    comment_host_templates_updated = 'Templates updated.'
    comment_host_templ_notupdated = 'Unable to update templates on host: {0}.'.format(host)
    comment_host_templates_in_sync = 'Templates already synced.'

    update_host_templates = False
    curr_template_ids = list()
    requested_template_ids = list()
    hostid = ''

    host_exists = __salt__['zabbix.host_exists'](host, **connection_args)

    # Fail out if host does not exist
    if not host_exists:
        ret['result'] = False
        ret['comment'] = comment_host_templ_notupdated
        return ret

    host_info = __salt__['zabbix.host_get'](host=host, **connection_args)[0]
    hostid = host_info['hostid']

    if not templates:
        templates = list()

    # Get current templateids for host
    host_templates = __salt__['zabbix.host_get'](hostids=hostid,
                                                 output='[{"hostid"}]',
                                                 selectParentTemplates='["templateid"]',
                                                 **connection_args)
    for template_id in host_templates[0]['parentTemplates']:
        curr_template_ids.append(template_id['templateid'])

    # Get requested templateids
    for template in templates:
        try:
            template_id = __salt__['zabbix.template_get'](host=template, **connection_args)[0]['templateid']
            requested_template_ids.append(template_id)
        except TypeError:
            ret['result'] = False
            ret['comment'] = 'Unable to find template: {0}.'.format(template)
            return ret

    # remove any duplications
    requested_template_ids = list(set(requested_template_ids))

    if set(curr_template_ids) != set(requested_template_ids):
        update_host_templates = True

    # Set change output
    changes_host_templates_modified = {host: {'old': 'Host templates: ' + ", ".join(curr_template_ids),
                                              'new': 'Host templates: ' + ', '.join(requested_template_ids)}}

    # Dry run, test=true mode
    if __opts__['test']:
        if update_host_templates:
            ret['result'] = None
            ret['comment'] = comment_host_templates_updated
        else:
            ret['result'] = True
            ret['comment'] = comment_host_templates_in_sync
        return ret

    # Attempt to perform update
    ret['result'] = True
    if update_host_templates:
        update_output = __salt__['zabbix.host_update'](hostid, templates=(requested_template_ids), **connection_args)
        if update_output is False:
            ret['result'] = False
            ret['comment'] = comment_host_templ_notupdated
            return ret
        ret['comment'] = comment_host_templates_updated
        ret['changes'] = changes_host_templates_modified
    else:
        ret['comment'] = comment_host_templates_in_sync

    return ret
