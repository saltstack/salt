# -*- coding: utf-8 -*-
'''
Management of LVS (Linux Virtual Server) Real Server
====================================================
'''


def __virtual__():
    '''
    Only load if the lvs module is available in __salt__
    '''
    return 'lvs_server' if 'lvs.get_rules' in __salt__ else False


def present(name,
            protocol=None,
            service_address=None,
            server_address=None,
            packet_forward_method='dr',
            weight=1
           ):
    '''
    Ensure that the named service is present.

    name
        The LVS server name

    protocol
        The service protocol

    service_address
        The LVS service address

    server_address
        The real server address.

    packet_forward_method
        The LVS packet forwarding method(``dr`` for direct routing, ``tunnel`` for tunneling, ``nat`` for network access translation).

    weight
        The capacity  of a server relative to the others in the pool.


    .. code-block:: yaml

        lvsrs:
          lvs_server.present:
            - protocol: tcp
            - service_address: 1.1.1.1:80
            - server_address: 192.168.0.11:8080
            - packet_forward_method: dr
            - weight: 10
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check server
    server_check = __salt__['lvs.check_server'](protocol=protocol,
                                                service_address=service_address,
                                                server_address=server_address)
    if server_check is True:
        server_rule_check = __salt__['lvs.check_server'](protocol=protocol,
                                                         service_address=service_address,
                                                         server_address=server_address,
                                                         packet_forward_method=packet_forward_method,
                                                         weight=weight)
        if server_rule_check is True:
            ret['comment'] = 'LVS Server {0} in service {1}({2}) is present'.format(name, service_address, protocol)
            return ret
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'LVS Server {0} in service {1}({2}) is present but some options should update'.format(name, service_address, protocol)
                return ret
            else:
                server_edit = __salt__['lvs.edit_server'](protocol=protocol,
                                                          service_address=service_address,
                                                          server_address=server_address,
                                                          packet_forward_method=packet_forward_method,
                                                          weight=weight)
                if server_edit is True:
                    ret['comment'] = 'LVS Server {0} in service {1}({2}) has been updated'.format(name, service_address, protocol)
                    ret['changes'][name] = 'Update'
                    return ret
                else:
                    ret['result'] = False
                    ret['comment'] = 'LVS Server {0} in service {1}({2}) update failed({3})'.format(name, service_address, protocol, server_edit)
                    return ret
    else:
        if __opts__['test']:
            ret['comment'] = 'LVS Server {0} in service {1}({2}) is not present and needs to be created'.format(name, service_address, protocol)
            ret['result'] = None
            return ret
        else:
            server_add = __salt__['lvs.add_server'](protocol=protocol,
                                                    service_address=service_address,
                                                    server_address=server_address,
                                                    packet_forward_method=packet_forward_method,
                                                    weight=weight)
            if server_add is True:
                ret['comment'] = 'LVS Server {0} in service {1}({2}) has been created'.format(name, service_address, protocol)
                ret['changes'][name] = 'Present'
                return ret
            else:
                ret['comment'] = 'LVS Service {0} in service {1}({2}) create failed({3})'.format(name, service_address, protocol, server_add)
                ret['result'] = False
                return ret


def absent(name, protocol=None, service_address=None, server_address=None):
    '''
    Ensure the LVS Real Server in specified service is absent.

    name
        The name of the LVS server.

    protocol
        The service protocol(only support ``tcp``, ``udp`` and ``fwmark`` service).

    service_address
        The LVS service address.

    server_address
        The LVS real server address.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if server exists and remove it
    server_check = __salt__['lvs.check_server'](protocol=protocol,
                                                service_address=service_address,
                                                server_address=server_address)
    if server_check is True:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'LVS Server {0} in service {1}({2}) is present and needs to be removed'.format(name, service_address, protocol)
            return ret
        server_delete = __salt__['lvs.delete_server'](protocol=protocol,
                                                      service_address=service_address,
                                                      server_address=server_address)
        if server_delete is True:
            ret['comment'] = 'LVS Server {0} in service {1}({2}) has been removed'.format(name, service_address, protocol)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['comment'] = 'LVS Server {0} in service {1}({2}) removed failed({3})'.format(name, service_address, protocol, server_delete)
            ret['result'] = False
            return ret
    else:
        ret['comment'] = 'LVS Server {0} in service {1}({2}) is not present, so it cannot be removed'.format(name, service_address, protocol)

    return ret
