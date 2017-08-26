def __virtual__():
    return 'keystone_role'


def _changes(role, **kwargs):
    changes = {}
    for k, v in role.items():
        if k in kwargs:
            if v != kwargs[k]:
                changes[k] = kwargs[k]
    return changes


def present(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    kwargs['name'] = name
    role = __salt__['keystoneng.role_get'](cloud=opcloud, **kwargs)
    
    if not role:
        role = __salt__['keystoneng.role_create'](cloud=opcloud, **kwargs)
        ret['changes']['id'] = role.id
        ret['changes']['name'] = role.name
        #ret['changes']['domain_id'] = role.domain_id
        ret['comment'] = 'Created role'
        return ret

    changes = __salt__['keystoneng.compare_changes'](role, **kwargs)
    if changes:
        __salt__['keystoneng.role_update'](cloud=opcloud, **kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated role'

    return ret


def absent(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)

    kwargs['name'] = name
    role = __salt__['keystoneng.role_get'](cloud=opcloud, **kwargs)

    if role:
        __salt__['keystoneng.role_delete'](cloud=opcloud, name=role)
        ret['changes']['id'] = role.id
        ret['comment'] = 'Deleted role'

    return ret
