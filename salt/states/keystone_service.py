def __virtual__():
    return 'keystone_service'


def present(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    service = __salt__['keystoneng.service_get'](cloud=opcloud, name=name)

    if service is None:
        kwargs['name'] = name
        service = __salt__['keystoneng.service_create'](cloud=opcloud, **kwargs)
        ret['changes'] = service
        ret['comment'] = 'Created service'
        return ret

    changes = __salt__['keystoneng.compare_changes'](service, **kwargs)
    if changes:
        kwargs['name'] = service
        __salt__['keystoneng.service_update'](cloud=opcloud, **kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated service'

    return ret


def absent(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    service = __salt__['keystoneng.service_get'](cloud=opcloud, name=name)

    if service:
        __salt__['keystoneng.service_delete'](cloud=opcloud, name=service)
        ret['changes']['id'] = service.id
        ret['comment'] = 'Deleted service'

    return ret
