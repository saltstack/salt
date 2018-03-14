# -*- coding: utf-8 -*-
'''
Management of OpenStack Keystone Projects
=========================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.keystoneng` for setup instructions

Example States

.. code-block:: yaml

    create project:
      keystone_project.present:
        - name: project1

    delete project:
      keystone_project.absent:
        - name: project1

    create project with optional params:
      keystone_project.present:
        - name: project1
        - domain: domain1
        - enabled: False
        - description: 'my project'
'''

from __future__ import absolute_import, unicode_literals, print_function

__virtualname__ = 'keystone_project'


def __virtual__():
    if 'keystoneng.project_get' in __salt__:
        return __virtualname__
    return (False, 'The keystoneng execution module failed to load: shade python module is not available')


def _common(name, kwargs):
    '''
    Returns: None if project wasn't found, otherwise a group object
    '''
    search_kwargs = {'name': name}
    if 'domain' in kwargs:
        domain = __salt__['keystoneng.get_entity'](
                          'domain', name=kwargs.pop('domain'))
        domain_id = domain.id if hasattr(domain, 'id') else domain
        search_kwargs['domain_id'] = domain_id
        kwargs['domain_id'] = domain_id

    return __salt__['keystoneng.project_get'](**search_kwargs)


def present(name, auth=None, **kwargs):
    '''
    Ensure a project exists and is up-to-date

    name
        Name of the project

    domain
        The name or id of the domain

    description
        An arbitrary description of the project
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    kwargs['name'] = name
    project = _common(name, kwargs)

    if project is None:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = kwargs
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Project will be created.'
            return ret

        project = __salt__['keystoneng.project_create'](**kwargs)
        ret['changes'] = project
        ret['comment'] = 'Created project'
        return ret

    changes = __salt__['keystoneng.compare_changes'](project, **kwargs)
    if changes:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = changes
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Project will be updated.'
            return ret

        __salt__['keystoneng.project_update'](**kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated project'

    return ret


def absent(name, auth=None, **kwargs):
    '''
    Ensure a project does not exists

    name
        Name of the project

    domain
        The name or id of the domain
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    kwargs['name'] = name
    project = _common(name, kwargs)

    if project:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = {'id': project.id}
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Project will be deleted.'
            return ret

        __salt__['keystoneng.project_delete'](name=project)
        ret['changes']['id'] = project.id
        ret['comment'] = 'Deleted project'

    return ret
