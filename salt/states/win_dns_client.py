# -*- coding: utf-8 -*-
'''
Module for configuring DNS Client on Windows systems
'''
from __future__ import absolute_import, unicode_literals, print_function


def __virtual__():
    '''
    Load if the module win_dns_client is loaded
    '''
    return 'win_dns_client' if 'win_dns_client.add_dns' in __salt__ else False


def dns_exists(name, servers=None, interface='Local Area Connection', replace=False):
    '''
    Configure the DNS server list in the specified interface

    Example:

    .. code-block:: yaml

        config_dns_servers:
          win_dns_client.dns_exists:
            - replace: True #remove any servers not in the "servers" list, default is False
            - servers:
              - 8.8.8.8
              - 8.8.8.9
    '''
    ret = {'name': name,
           'result': True,
           'changes': {'Servers Reordered': [], 'Servers Added': [], 'Servers Removed': []},
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'DNS Servers are set to be updated'
        ret['result'] = None
    else:
        ret['comment'] = 'DNS Servers have been updated'

    # Validate syntax
    if not isinstance(servers, list):
        ret['result'] = False
        ret['comment'] = 'servers entry is not a list !'
        return ret

    # Do nothing is already configured
    configured_list = __salt__['win_dns_client.get_dns_servers'](interface)
    if configured_list == servers:
        ret['comment'] = '{0} are already configured'.format(servers)
        ret['changes'] = {}
        ret['result'] = True
        return ret

    # add the DNS servers
    for i, server in enumerate(servers):
        if __opts__['test']:
            if server in configured_list:
                if configured_list.index(server) != i:
                    ret['changes']['Servers Reordered'].append(server)
            else:
                ret['changes']['Servers Added'].append(server)
        else:
            if not __salt__['win_dns_client.add_dns'](server, interface, i + 1):
                ret['comment'] = (
                        'Failed to add {0} as DNS server number {1}'
                        ).format(server, i + 1)
                ret['result'] = False
                ret['changes'] = {}
                return ret
            else:
                if server in configured_list:
                    if configured_list.index(server) != i:
                        ret['changes']['Servers Reordered'].append(server)
                else:
                    ret['changes']['Servers Added'].append(server)

    # remove dns servers that weren't in our list
    if replace:
        for i, server in enumerate(configured_list):
            if server not in servers:
                if __opts__['test']:
                    ret['changes']['Servers Removed'].append(server)
                else:
                    if not __salt__['win_dns_client.rm_dns'](server, interface):
                        ret['comment'] = (
                                'Failed to remove {0} from DNS server list').format(server)
                        ret['result'] = False
                        return ret
                    else:
                        ret['changes']['Servers Removed'].append(server)

    return ret


def dns_dhcp(name, interface='Local Area Connection'):
    '''
    Configure the DNS server list from DHCP Server
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Check the config
    config = __salt__['win_dns_client.get_dns_config'](interface)
    if config == 'dhcp':
        ret['comment'] = '{0} already configured with DNS from DHCP'.format(
                interface)
        return ret
    else:
        ret['changes'] = {'dns': 'configured from DHCP'}

    if __opts__['test']:
        ret['result'] = None
        return ret

    # change the configuration
    ret['result'] = __salt__['win_dns_client.dns_dhcp'](interface)
    if not ret['result']:
        ret['changes'] = {}
        ret['comment'] = (
                'Could not configure "{0}" DNS servers from DHCP'
                ).format(interface)

    return ret


def primary_suffix(name,
        suffix=None,
        updates=False):
    '''
    .. versionadded:: 2014.7.0

    Configure the global primary DNS suffix of a DHCP client.

    suffix : None
        The suffix which is advertised for this client when acquiring a DHCP lease
        When none is set, the explicitly configured DNS suffix will be removed.

    updates : False
        Allow syncing the DNS suffix with the AD domain when the client's AD domain membership changes

    .. code-block:: yaml

        primary_dns_suffix:
            win_dns_client.primary_suffix:
                - suffix: sub.domain.tld
                - updates: True
    '''

    ret = {
            'name': name,
            'changes': {},
            'result': True,
            'comment': 'No changes needed'
    }

    suffix = str(suffix)

    if not isinstance(updates, bool):
        ret['result'] = False
        ret['comment'] = '\'updates\' must be a boolean value'
        return ret

    # TODO: waiting for an implementation of
    # https://github.com/saltstack/salt/issues/6792 to be able to handle the
    # requirement for a reboot to actually apply this state.
    # Until then, this method will only be able to verify that the required
    # value has been written to the registry and rebooting needs to be handled
    # manually

    reg_data = {
            'suffix': {
                'hive': 'HKEY_LOCAL_MACHINE',
                'key': r'SYSTEM\CurrentControlSet\services\Tcpip\Parameters',
                'vname':  'NV Domain',
                'vtype': 'REG_SZ',
                'old':  None,
                'new':  suffix
            },
            'updates': {
                'hive': 'HKEY_LOCAL_MACHINE',
                'key': r'SYSTEM\CurrentControlSet\services\Tcpip\Parameters',
                'vname':  'SyncDomainWithMembership',
                'vtype': 'REG_DWORD',
                'old':  None,
                'new':  updates
            }
    }

    reg_data['suffix']['old'] = __salt__['reg.read_value'](
            reg_data['suffix']['hive'],
            reg_data['suffix']['key'],
            reg_data['suffix']['vname'],)['vdata']

    reg_data['updates']['old'] = bool(__salt__['reg.read_value'](
            reg_data['updates']['hive'],
            reg_data['updates']['key'],
            reg_data['updates']['vname'],)['vdata'])

    updates_operation = 'enabled' if reg_data['updates']['new'] else 'disabled'

    # No changes to suffix needed
    if reg_data['suffix']['new'] == reg_data['suffix']['old']:
        # No changes to updates policy needed
        if reg_data['updates']['new'] == reg_data['updates']['old']:
            return ret
        # Changes to update policy needed
        else:
            ret['comment'] = '{0} suffix updates'.format(updates_operation)
            ret['changes'] = {
                    'old': {
                        'updates': reg_data['updates']['old']},
                    'new': {
                        'updates': reg_data['updates']['new']}}
    # Changes to suffix needed
    else:
        # Changes to updates policy needed
        if reg_data['updates']['new'] != reg_data['updates']['old']:
            ret['comment'] = 'Updated primary DNS suffix ({0}) and {1} suffix updates'.format(suffix, updates_operation)
            ret['changes'] = {
                    'old': {
                        'suffix': reg_data['suffix']['old'],
                        'updates': reg_data['updates']['old']},
                    'new': {
                        'suffix': reg_data['suffix']['new'],
                        'updates': reg_data['updates']['new']}}
        # No changes to updates policy needed
        else:
            ret['comment'] = 'Updated primary DNS suffix ({0})'.format(suffix)
            ret['changes'] = {
                    'old': {
                        'suffix': reg_data['suffix']['old']},
                    'new': {
                        'suffix': reg_data['suffix']['new']}}

    suffix_result = __salt__['reg.set_value'](
            reg_data['suffix']['hive'],
            reg_data['suffix']['key'],
            reg_data['suffix']['vname'],
            reg_data['suffix']['new'],
            reg_data['suffix']['vtype'])

    updates_result = __salt__['reg.set_value'](
            reg_data['updates']['hive'],
            reg_data['updates']['key'],
            reg_data['updates']['vname'],
            reg_data['updates']['new'],
            reg_data['updates']['vtype'])

    ret['result'] = suffix_result & updates_result

    return ret
