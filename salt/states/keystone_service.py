def __virtual__():
    return 'keystone_service'


def present(name, auth=None, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    service = __salt__['keystoneng.service_get'](name=name)

    if service is None:
        kwargs['name'] = name
        service = __salt__['keystoneng.service_create'](**kwargs)
        ret['changes'] = service
        ret['comment'] = 'Created service'
        return ret

    changes = __salt__['keystoneng.compare_changes'](service, **kwargs)
    if changes:
        kwargs['name'] = service
        __salt__['keystoneng.service_update'](**kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated service'

    return ret


def absent(name, auth=None):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    service = __salt__['keystoneng.service_get'](name=name)

    if service:
        __salt__['keystoneng.service_delete'](name=service)
        ret['changes']['id'] = service.id
        ret['comment'] = 'Deleted service'

    return ret
