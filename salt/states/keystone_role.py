# -*- coding: utf-8 -*-
'''
Management of OpenStack Keystone Roles
======================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.keystoneng` for setup instructions

Example States

.. code-block:: yaml

    create role:
      keystone_role.present:
        - name: role1

    delete role:
      keystone_role.absent:
        - name: role1

    create role with optional params:
      keystone_role.present:
        - name: role1
        - description: 'my group'
'''

from __future__ import absolute_import, unicode_literals, print_function

__virtualname__ = 'keystone_role'


def __virtual__():
    if 'keystoneng.role_get' in __salt__:
        return __virtualname__
    return (False, 'The keystoneng execution module failed to load: shade python module is not available')


def present(name, auth=None, **kwargs):
    '''
    Ensure an role exists

    name
        Name of the role

    description
        An arbitrary description of the role
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    kwargs['name'] = name
    role = __salt__['keystoneng.role_get'](**kwargs)

    if not role:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = kwargs
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Role will be created.'
            return ret

        role = __salt__['keystoneng.role_create'](**kwargs)
        ret['changes']['id'] = role.id
        ret['changes']['name'] = role.name
        ret['comment'] = 'Created role'
        return ret
    # NOTE(SamYaple): Update support pending https://review.openstack.org/#/c/496992/
    return ret


def absent(name, auth=None, **kwargs):
    '''
    Ensure role does not exist

    name
        Name of the role
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    kwargs['name'] = name
    role = __salt__['keystoneng.role_get'](**kwargs)

    if role:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = {'id': role.id}
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Role will be deleted.'
            return ret

        __salt__['keystoneng.role_delete'](name=role)
        ret['changes']['id'] = role.id
        ret['comment'] = 'Deleted role'

    return ret
