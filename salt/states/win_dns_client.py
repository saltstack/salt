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
    Configure the dns server list in the specified interface
    
    Example::

        config_dns_servers:
          network_win.dns_exists:
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
        return ret
    
    # add the dns servers
    for i in range(0, len(servers)):
        if not __salt__['win_dns_client.add_dns'](servers[i] ,interface, i+1):
            ret['comment'] = (
                    'Failed to add {0} as dns server number {1}'
                    ).format(servers[i] ,i+1)
            ret['result'] = False
            if i != 0:
                ret['changes'] = {'configure servers': servers[0,i]}
            else:
                ret['changes'] = {}
            return ret
    
    return ret


def dns_dhcp(name, interface='Local Area Connection'):
    '''
    Configure the dns server list from DHCP Server
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    
    # Check the config
    config = __salt__['win_dns_client.get_dns_config'](interface)
    if config == 'dhcp':
        ret['comment'] = '{0} already configured with dns from dhcp'.format(
                interface)
        return ret
    else:
        ret['changes'] = {'dns': 'configured from dhcp'}
    
    if __opts__['test']:
        return ret
    
    # change the configuration
    ret['result'] = __salt__['win_dns_client.dns_dhcp'](interface)
    if not ret['result']:
        ret['changes'] = {}
        ret['comment'] = (
                'Could not configure "{0}" dns servers from dhcp'
                ).format(interface)
    
    return ret
    

