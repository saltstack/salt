# -*- coding: utf-8 -*-
'''
Module for configuring DNS Client on Windows systems
'''


def __virtual__():
    '''
    Load if the module win_dns_client is loaded
    '''
    return 'win_dns_client' if 'win_dns_client.add_dns' in __salt__ else False


def dns_exists(name, servers=None, interface='Local Area Connection'):
    '''
    Configure the DNS server list in the specified interface

    Example::

        config_dns_servers:
          win_dns_client.dns_exists:
            - servers:
              - 8.8.8.8
              - 8.8.8.9
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Validate syntax
    if type(servers) != list:
        ret['result'] = False
        ret['comment'] = 'servers entry is not a list !'
        return ret

    # Do nothing is already configured
    configured_list = __salt__['win_dns_client.get_dns_servers'](interface)
    if configured_list == servers:
        ret['comment'] = '{0} are already configured'.format(servers)
        return ret
    else:
        ret['changes'] = {'configure servers': servers}

    if __opts__['test']:
        ret['result'] = None
        return ret

    # add the DNS servers
    for i, server in enumerate(servers):
        if not __salt__['win_dns_client.add_dns'](server, interface, i + 1):
            ret['comment'] = (
                    'Failed to add {0} as DNS server number {1}'
                    ).format(server, i + 1)
            ret['result'] = False
            if i > 0:
                ret['changes'] = {'configure servers': servers[:i]}
            else:
                ret['changes'] = {}
            return ret

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
