def __virtual__():
    return 'keystone_domain'


def present(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    domain = __salt__['keystoneng.domain_get'](cloud=opcloud, name=name)
    
    if not domain:
        kwargs['name'] = name
        domain = __salt__['keystoneng.domain_create'](cloud=opcloud, **kwargs)
        ret['changes'] = domain
        ret['comment'] = 'Created domain'
        return ret

    changes = __salt__['keystoneng.compare_changes'](domain, **kwargs)
    if changes:
        kwargs['domain_id'] = domain.id
        __salt__['keystoneng.domain_update'](cloud=opcloud, **kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated domain'

    return ret


def absent(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    domain = __salt__['keystoneng.domain_get'](cloud=opcloud, name=name)

    if domain:
        __salt__['keystoneng.domain_delete'](cloud=opcloud, name=domain)
        ret['changes']['id'] = domain.id
        ret['comment'] = 'Deleted domain'

    return ret
