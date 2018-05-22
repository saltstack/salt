# -*- coding: utf-8 -*-
'''
Management of OpenStack Keystone Role Grants
============================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.keystoneng` for setup instructions

Example States

.. code-block:: yaml

    create group:
      keystone_group.present:
        - name: group1

    delete group:
      keystone_group.absent:
        - name: group1

    create group with optional params:
      keystone_group.present:
        - name: group1
        - domain: domain1
        - description: 'my group'
'''

from __future__ import absolute_import, unicode_literals, print_function

__virtualname__ = 'keystone_role_grant'


def __virtual__():
    if 'keystoneng.role_grant' in __salt__:
        return __virtualname__
    return (False, 'The keystoneng execution module failed to load: shade python module is not available')


def _get_filters(kwargs):
    role_kwargs = {'name': kwargs.pop('role')}
    if 'role_domain' in kwargs:
        domain = __salt__['keystoneng.get_entity'](
                          'domain', name=kwargs.pop('role_domain'))
        if domain:
            role_kwargs['domain_id'] = domain.id \
                if hasattr(domain, 'id') else domain
    role = __salt__['keystoneng.role_get'](**role_kwargs)
    kwargs['name'] = role
    filters = {'role': role.id if hasattr(role, 'id') else role}

    if 'domain' in kwargs:
        domain = __salt__['keystoneng.get_entity'](
                  'domain', name=kwargs.pop('domain'))
        kwargs['domain'] = filters['domain'] = \
                domain.id if hasattr(domain, 'id') else domain

    if 'project' in kwargs:
        project_kwargs = {'name': kwargs.pop('project')}
        if 'project_domain' in kwargs:
            domain = __salt__['keystoneng.get_entity'](
                              'domain', name=kwargs.pop('project_domain'))
            if domain:
                project_kwargs['domain_id'] = domain.id
        project = __salt__['keystoneng.get_entity'](
                           'project', **project_kwargs)
        kwargs['project'] = project
        filters['project'] = project.id if hasattr(project, 'id') else project

    if 'user' in kwargs:
        user_kwargs = {'name': kwargs.pop('user')}
        if 'user_domain' in kwargs:
            domain = __salt__['keystoneng.get_entity'](
                              'domain', name=kwargs.pop('user_domain'))
            if domain:
                user_kwargs['domain_id'] = domain.id
        user = __salt__['keystoneng.get_entity']('user', **user_kwargs)
        kwargs['user'] = user
        filters['user'] = user.id if hasattr(user, 'id') else user

    if 'group' in kwargs:
        group_kwargs = {'name': kwargs['group']}
        if 'group_domain' in kwargs:
            domain = __salt__['keystoneng.get_entity'](
                              'domain', name=kwargs.pop('group_domain'))
            if domain:
                group_kwargs['domain_id'] = domain.id
        group = __salt__['keystoneng.get_entity']('group', **group_kwargs)

        kwargs['group'] = group
        filters['group'] = group.id if hasattr(group, 'id') else group

    return filters, kwargs


def present(name, auth=None, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    if 'role' not in kwargs:
        kwargs['role'] = name
    filters, kwargs = _get_filters(kwargs)

    grants = __salt__['keystoneng.role_assignment_list'](filters=filters)

    if not grants:
        __salt__['keystoneng.role_grant'](**kwargs)
        for k, v in filters.items():
            ret['changes'][k] = v
        ret['comment'] = 'Granted role assignment'

    return ret


def absent(name, auth=None, **kwargs):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    if 'role' not in kwargs:
        kwargs['role'] = name
    filters, kwargs = _get_filters(kwargs)

    grants = __salt__['keystoneng.role_assignment_list'](filters=filters)

    if grants:
        __salt__['keystoneng.role_revoke'](**kwargs)
        for k, v in filters.items():
            ret['changes'][k] = v
        ret['comment'] = 'Revoked role assignment'

    return ret
