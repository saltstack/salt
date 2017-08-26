def __virtual__():
    return 'keystone_project'


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
    project = __salt__['keystoneng.project_get'](cloud=oscloud,
                                                 **search_kwargs)

    kwargs['name'] = name
    if project is None:
        project = __salt__['keystoneng.project_create'](cloud=oscloud, **kwargs)
        ret['changes'] = project
        ret['comment'] = 'Created project'
        return ret

    changes = __salt__['keystoneng.compare_changes'](project, **kwargs)
    if changes:
        __salt__['keystoneng.project_update'](cloud=opcloud, **kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated project'

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
    project = __salt__['keystoneng.project_get'](cloud=oscloud,
                                                 **search_kwargs)

    if project:
        __salt__['keystoneng.project_delete'](cloud=opcloud, name=project)
        ret['changes']['id'] = project.id
        ret['comment'] = 'Deleted project'

    return ret
