def __virtual__():
    return 'keystone_endpoint'


def present(name, service_name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    if 'interface' not in kwargs and 'public_url' not in kwargs:
        kwargs['interface'] = name
    service = __salt__['keystoneng.service_get'](cloud=opcloud,
                                                 name_or_id=service_name)
    if not service:
        ret['comment'] = 'Cannot find service'
        ret['result'] = False
        return ret
    filters = kwargs.copy()
    filters.pop('enabled', None)
    filters['service_id'] = service.id
    endpoint = __salt__['keystoneng.endpoint_get'](cloud=opcloud,
                                                   filters=filters)
    
    kwargs['service_name_or_id'] = service
    if not endpoint:
        # Endpoints are returned as a list which can container several items
        endpoints = __salt__['keystoneng.endpoint_create'](cloud=opcloud, **kwargs)
        if len(endpoints) == 1:
            ret['changes'] = endpoints[0]
        else:
            for i, endpoint in enumerate(endpoints):
                ret['changes'][i] = endpoint
        ret['comment'] = 'Created endpoint'
        return ret

    changes = __salt__['keystoneng.compare_changes'](endpoint, **kwargs)
    if changes:
        kwargs['endpoint_id'] = endpoint.id
        __salt__['keystoneng.endpoint_update'](cloud=opcloud, **kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated endpoint'

    return ret


def absent(name, service_name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    if 'interface' not in kwargs and 'public_url' not in kwargs:
        kwargs['interface'] = name
    service = __salt__['keystoneng.service_get'](cloud=opcloud,
                                                 name_or_id=service_name)
    if not service:
        ret['comment'] = 'Cannot find service'
        ret['result'] = False
        return ret
    filters = kwargs.copy()
    filters.pop('enabled', None)
    filters['service_id'] = service.id
    endpoint = __salt__['keystoneng.endpoint_get'](cloud=opcloud,
                                                   filters=filters)
    
    if endpoint:
        __salt__['keystoneng.endpoint_delete'](cloud=opcloud, id=endpoint)
        ret['changes']['id'] = endpoint.id
        ret['comment'] = 'Deleted endpoint'

    return ret
