def __virtual__():
    return 'keystone_user'


def present(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)
    oscloud = __salt__['keystoneng.get_openstack_cloud'](auth)

    search_kwargs = {'name': name}
    if 'domain' in kwargs:
        domain = __salt__['keystoneng.get_entity'](
                opcloud, 'domain', name=kwargs.pop('domain'))
        domain_id = domain.id if hasattr(domain, 'id') else domain
        search_kwargs['domain_id'] = domain_id
        kwargs['domain_id'] = domain_id
    user = __salt__['keystoneng.user_get'](cloud=oscloud, **search_kwargs)

    if user is None:
        kwargs['name'] = name
        user = __salt__['keystoneng.user_create'](cloud=oscloud, **kwargs)
        ret['changes'] = user
        ret['comment'] = 'Created user'
        return ret

    changes = __salt__['keystoneng.compare_changes'](user, **kwargs)
    if changes:
        kwargs['name'] = user
        __salt__['keystoneng.user_update'](cloud=oscloud, **kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated user'

    return ret


def absent(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)
    oscloud = __salt__['keystoneng.get_openstack_cloud'](auth)

    search_kwargs = {'name': name}
    if 'domain' in kwargs:
        domain = __salt__['keystoneng.get_entity'](
                opcloud, 'domain', name=kwargs.pop('domain'))
        domain_id = domain.id if hasattr(domain, 'id') else domain
        search_kwargs['domain_id'] = domain_id
        kwargs['domain_id'] = domain_id
    user = __salt__['keystoneng.user_get'](cloud=oscloud, **search_kwargs)

    if user:
        __salt__['keystoneng.user_delete'](cloud=oscloud, name=user)
        ret['changes']['id'] = user.id
        ret['comment'] = 'Deleted user'

    return ret
