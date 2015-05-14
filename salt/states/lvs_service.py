# -*- coding: utf-8 -*-
'''
Management of LVS (Linux Virtual Server) Service
================================================
'''


def __virtual__():
    '''
    Only load if the lvs module is available in __salt__
    '''
    return 'lvs_service' if 'lvs.get_rules' in __salt__ else False


def present(name,
            protocol=None,
            service_address=None,
            scheduler='wlc',
           ):
    '''
    Ensure that the named service is present.

    name
        The LVS service name

    protocol
        The service protocol

    service_address
        The LVS service address

    scheduler
        Algorithm for allocating TCP connections and UDP datagrams to real servers.

    .. code-block:: yaml

        lvstest:
          lvs_service.present:
            - service_address: 1.1.1.1:80
            - protocol: tcp
            - scheduler: rr
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check service
    service_check = __salt__['lvs.check_service'](protocol=protocol,
                                                  service_address=service_address)
    if service_check is True:
        service_rule_check = __salt__['lvs.check_service'](protocol=protocol,
                                                           service_address=service_address,
                                                           scheduler=scheduler)
        if service_rule_check is True:
            ret['comment'] = 'LVS Service {0} is present'.format(name)
            return ret
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'LVS Service {0} is present but some options should update'.format(name)
                return ret
            else:
                service_edit = __salt__['lvs.edit_service'](protocol=protocol,
                                                            service_address=service_address,
                                                            scheduler=scheduler)
                if service_edit is True:
                    ret['comment'] = 'LVS Service {0} has been updated'.format(name)
                    ret['changes'][name] = 'Update'
                    return ret
                else:
                    ret['result'] = False
                    ret['comment'] = 'LVS Service {0} update failed'.format(name)
                    return ret
    else:
        if __opts__['test']:
            ret['comment'] = 'LVS Service {0} is not present and needs to be created'.format(name)
            ret['result'] = None
            return ret
        else:
            service_add = __salt__['lvs.add_service'](protocol=protocol,
                                                      service_address=service_address,
                                                      scheduler=scheduler)
            if service_add is True:
                ret['comment'] = 'LVS Service {0} has been created'.format(name)
                ret['changes'][name] = 'Present'
                return ret
            else:
                ret['comment'] = 'LVS Service {0} create failed({1})'.format(name, service_add)
                ret['result'] = False
                return ret


def absent(name, protocol=None, service_address=None):
    '''
    Ensure the LVS service is absent.

    name
        The name of the LVS service

    protocol
        The service protocol

    service_address
        The LVS service address
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if service exists and remove it
    service_check = __salt__['lvs.check_service'](protocol=protocol,
                                                  service_address=service_address)
    if service_check is True:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'LVS Service {0} is present and needs to be removed'.format(name)
            return ret
        service_delete = __salt__['lvs.delete_service'](protocol=protocol,
                                                        service_address=service_address)
        if service_delete is True:
            ret['comment'] = 'LVS Service {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['comment'] = 'LVS Service {0} removed failed({1})'.format(name, service_delete)
            ret['result'] = False
            return ret
    else:
        ret['comment'] = 'LVS Service {0} is not present, so it cannot be removed'.format(name)

    return ret
