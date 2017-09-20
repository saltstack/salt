def __virtual__():
    return 'keystone_endpoint'


def present(name, service, auth=None, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    if 'interface' not in kwargs and 'public_url' not in kwargs:
        kwargs['interface'] = name
    service = __salt__['keystoneng.service_get'](name_or_id=service)

    if not service:
        ret['comment'] = 'Cannot find service'
        ret['result'] = False
        return ret

    filters = kwargs.copy()
    filters.pop('enabled', None)
    filters['service_id'] = service.id
    endpoints = __salt__['keystoneng.endpoint_search'](filters=filters)

    if len(endpoints) > 1:
        ret['comment'] = "Multiple endpoints match criteria"
        ret['result'] = False
        return ret
    endpoint = endpoints[0] if endpoints else None
    
    kwargs['service_name_or_id'] = service
    if not endpoint:
        # Endpoints are returned as a list which can container several items
        endpoints = __salt__['keystoneng.endpoint_create'](**kwargs)
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
        __salt__['keystoneng.endpoint_update'](**kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated endpoint'

    return ret


def absent(name, service, auth=None, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    if 'interface' not in kwargs and 'public_url' not in kwargs:
        kwargs['interface'] = name
    service = __salt__['keystoneng.service_get'](name_or_id=service)

    if not service:
        ret['comment'] = 'Cannot find service'
        ret['result'] = False
        return ret

    filters = kwargs.copy()
    filters.pop('enabled', None)
    filters['service_id'] = service.id
    endpoints = __salt__['keystoneng.endpoint_search'](filters=filters)
    
    if len(endpoints) > 1:
        ret['comment'] = "Multiple endpoints match criteria"
        ret['result'] = False
        return ret
    endpoint = endpoints[0] if endpoints else None

    if endpoint:
        __salt__['keystoneng.endpoint_delete'](id=endpoint)
        ret['changes']['id'] = endpoint.id
        ret['comment'] = 'Deleted endpoint'

    return ret
