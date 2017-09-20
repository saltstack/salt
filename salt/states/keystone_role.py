def __virtual__():
    return 'keystone_role'


def _changes(role, **kwargs):
    changes = {}
    for k, v in role.items():
        if k in kwargs:
            if v != kwargs[k]:
                changes[k] = kwargs[k]
    return changes


def present(name, auth=None, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    kwargs['name'] = name
    role = __salt__['keystoneng.role_get'](**kwargs)
    
    if not role:
        role = __salt__['keystoneng.role_create'](**kwargs)
        ret['changes']['id'] = role.id
        ret['changes']['name'] = role.name
        #ret['changes']['domain_id'] = role.domain_id
        ret['comment'] = 'Created role'
        return ret

    changes = __salt__['keystoneng.compare_changes'](role, **kwargs)
    if changes:
        __salt__['keystoneng.role_update'](**kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated role'

    return ret


def absent(name, auth=None, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    kwargs['name'] = name
    role = __salt__['keystoneng.role_get'](**kwargs)

    if role:
        __salt__['keystoneng.role_delete'](name=role)
        ret['changes']['id'] = role.id
        ret['comment'] = 'Deleted role'

    return ret
