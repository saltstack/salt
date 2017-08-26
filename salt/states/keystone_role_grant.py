def __virtual__():
    return 'keystone_role_grant'

def _get_filters(opcloud, oscloud, kwargs):
    role_kwargs = {'name': kwargs.pop('role')}
    if 'role_domain' in kwargs:
        domain = __salt__['keystoneng.get_entity'](
	        opcloud, 'domain', name=kwargs.pop('role_domain'))
        role_kwargs['domain_id'] = domain.id \
                if hasattr(domain, 'id') else domain
    role = __salt__['keystoneng.role_get'](cloud=opcloud, **role_kwargs)
    kwargs['name'] = role
    filters = {'role': role.id if hasattr(role, 'id') else role}

    if 'domain' in kwargs:
        domain = __salt__['keystoneng.get_entity'](
		opcloud, 'domain', name=kwargs.pop('domain'))
        kwargs['domain'] = domain
        filters['domain'] = domain.id if hasattr(domain, 'id') else domain

    if 'project' in kwargs:
        project_kwargs = {'name': kwargs['project']}
        if 'project_domain' in kwargs:
            domain = __salt__['keystoneng.get_entity'](
                    opcloud, 'domain', name=kwargs.pop('project_domain'))
            kwargs['project_domain'] = domain
            project_kwargs['domain'] = domain
        project = __salt__['keystoneng.get_entity'](
		oscloud, 'project', name=kwargs.pop('project'))
        kwargs['project'] = project
        filters['project'] = project.id if hasattr(project, 'id') else project

    if 'user' in kwargs:
        user_kwargs = {'name': kwargs['user']}
        if 'user_domain' in kwargs:
            domain = __salt__['keystoneng.get_entity'](
                    opcloud, 'domain', name=kwargs.pop('user_domain'))
            kwargs['user_domain'] = domain
            user_kwargs['domain'] = domain
        user = __salt__['keystoneng.get_entity'](
		oscloud, 'user', name=kwargs.pop('user'))
        kwargs['user'] = user
        filters['user'] = user.id if hasattr(user, 'id') else user

    if 'group' in kwargs:
        group_kwargs = {'name': kwargs['group']}
        if 'group_domain' in kwargs:
            domain = __salt__['keystoneng.get_entity'](
                    opcloud, 'domain', name=kwargs.pop('group_domain'))
            kwargs['group_domain'] = domain
            user_kwargs['domain'] = domain
        user = __salt__['keystoneng.get_entity'](
		opcloud, 'group', name=kwargs.pop('group'))
        kwargs['group'] = group
        filters['group'] = group.id if hasattr(group, 'id') else group

    return filters, kwargs

def present(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)
    oscloud = __salt__['keystoneng.get_openstack_cloud'](auth)

    if 'role' not in kwargs:
        kwargs['role'] = name
    filters, kwargs = _get_filters(opcloud, oscloud, kwargs)

    grants = __salt__['keystoneng.role_assignment_list'](cloud=opcloud,
                                                         filters=filters)
    if not grants:
        __salt__['keystoneng.role_grant'](cloud=opcloud, **kwargs)
        for k, v in filters.items():
            ret['changes'][k] = v
        ret['comment'] = 'Granted role assignment'

    return ret


def absent(name, auth, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    opcloud = __salt__['keystoneng.get_operator_cloud'](auth)
    oscloud = __salt__['keystoneng.get_openstack_cloud'](auth)

    if 'role' not in kwargs:
        kwargs['role'] = name
    filters, kwargs = _get_filters(opcloud, oscloud, kwargs)

    grants = __salt__['keystoneng.role_assignment_list'](cloud=opcloud,
                                                         filters=filters)
    if grants:
        __salt__['keystoneng.role_revoke'](cloud=opcloud, **kwargs)
        for k, v in filters.items():
            ret['changes'][k] = v
        ret['comment'] = 'Revoked role assignment'

    return ret
