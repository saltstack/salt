def __virtual__():
    return 'keystone_group'


def present(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    search_kwargs = {'name': name}
    if 'domain' in kwargs:
        kwargs['domain_id'] = __salt__['keystoneng.get_entity'](
                opcloud, 'domain', name=kwargs.pop('domain'))
        search_kwargs['filters'] = {'domain_id': kwargs['domain_id']}

    group = __salt__['keystoneng.group_get'](cloud=opcloud, **search_kwargs)

    kwargs['name'] = name
    if group is None:
        group = __salt__['keystoneng.group_create'](cloud=opcloud, **kwargs)
        ret['changes'] = group
        ret['comment'] = 'Created group'
        return ret

    changes = __salt__['keystoneng.compare_changes'](group, **kwargs)
    if changes:
        __salt__['keystoneng.group_update'](cloud=opcloud, **kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated group'

    return ret


def absent(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    search_kwargs = {'name': name}
    if 'domain' in kwargs:
        kwargs['domain_id'] = __salt__['keystoneng.get_entity'](
                opcloud, 'domain', name=kwargs.pop('domain'))
        search_kwargs['filters'] = {'domain_id': kwargs['domain_id']}

    group = __salt__['keystoneng.group_get'](cloud=opcloud, **search_kwargs)

    if group:
        __salt__['keystoneng.group_delete'](cloud=opcloud, name=group)
        ret['changes']['id'] = group.id
        ret['comment'] = 'Deleted group'

    return ret
