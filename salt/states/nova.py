# -*- coding: utf-8 -*-
'''
.. versionadded:: 2017.7

Module for handling OpenStack Nova calls

:codeauthor: Jakub Sliva <jakub.sliva@ultimum.io>
'''
from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only make these states available if nova module is available
    '''
    if 'nova.flavor_list' in __salt__:
        return True
    return False, 'nova execution module not imported properly.'


def flavor_present(name, params=None, **kwargs):
    '''
    Creates Nova flavor if it does not exist

    :param name: Flavor name
    :param params: Definition of the Flavor (see Compute API documentation)

    .. code-block:: yaml

        nova-flavor-present:
            nova.flavor_present:
                - name: myflavor
                - params:
                    ram: 2
                    vcpus: 1
                    disk: 10
                    is_public: False
    '''
    dry_run = __opts__['test']
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    if params is None:
        params = {}

    try:
        kwargs.update({'filter': {'is_public': None}})
        object_list = __salt__['nova.flavor_list'](**kwargs)
        object_exists = True if object_list[name]['name'] == name else False
    except KeyError:
        object_exists = False

    if object_exists:
        ret['result'] = True
        ret['comment'] = 'Flavor "{0}" already exists.'.format(name)
    else:
        if dry_run:
            ret['result'] = None
            ret['comment'] = 'Flavor "{0}" would be created.'.format(name)
            ret['changes'] = {name: {'old': 'Flavor "{0}" does not exist.'.format(name),
                                     'new': params}}
        else:
            combined = kwargs.copy()
            combined.update(params)
            flavor_create = __salt__['nova.flavor_create'](name, **combined)

            if flavor_create:
                ret['result'] = True
                ret['comment'] = 'Flavor "{0}" created.'.format(name)
                ret['changes'] = {name: {'old': 'Flavor "{0}" does not exist.'.format(name),
                                         'new': flavor_create}}

    return ret


def flavor_access_list(name, projects, **kwargs):
    '''
    Grants access of the flavor to a project. Flavor must be private.

    :param name: non-public flavor name
    :param projects: list of projects which should have the access to the flavor

    .. code-block:: yaml

        nova-flavor-share:
            nova.flavor_project_access:
                - name: myflavor
                - project:
                    - project1
                    - project2

    To remove all project from access list:

    .. code-block:: yaml

        - project: []
    '''
    dry_run = __opts__['test']
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    kwargs.update({'filter': {'is_public': False}})
    try:
        flavor_list = __salt__['nova.flavor_list'](**kwargs)
        flavor_id = flavor_list[name]['id']
    except KeyError:
        raise

    project_list = __salt__['keystone.project_list'](**kwargs)
    access_list = __salt__['nova.flavor_access_list'](flavor_id, **kwargs)
    existing_list = [six.text_type(pname) for pname in project_list
                     if project_list[pname]['id'] in access_list[flavor_id]]
    defined_list = [six.text_type(project) for project in projects]
    add_list = set(defined_list) - set(existing_list)
    remove_list = set(existing_list) - set(defined_list)

    if not add_list and not remove_list:
        ret['result'] = True
        ret['comment'] = 'Flavor "{0}" access list corresponds to defined one.'.format(name)
    else:
        if dry_run:
            ret['result'] = None
            ret['comment'] = 'Flavor "{0}" access list would be corrected.'.format(name)
            ret['changes'] = {name: {'new': defined_list, 'old': existing_list}}
        else:
            added = []
            removed = []
            if add_list:
                for project in add_list:
                    added.append(__salt__['nova.flavor_access_add'](flavor_id, project_list[project]['id'], **kwargs))
            if remove_list:
                for project in remove_list:
                    removed.append(__salt__['nova.flavor_access_remove'](flavor_id,
                                                                         project_list[project]['id'], **kwargs))
            if any(add_list) or any(remove_list):
                ret['result'] = True
                ret['comment'] = 'Flavor "{0}" access list corrected.'.format(name)
                ret['changes'] = {name: {'new': defined_list, 'old': existing_list}}

    return ret


def flavor_absent(name, **kwargs):
    '''
    Makes flavor to be absent

    :param name: flavor name

    .. code-block:: yaml

        nova-flavor-absent:
            nova.flavor_absent:
                - name: flavor_name
    '''
    dry_run = __opts__['test']
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    try:
        object_list = __salt__['nova.flavor_list'](**kwargs)
        object_id = object_list[name]['id']
    except KeyError:
        object_id = False

    if not object_id:
        ret['result'] = True
        ret['comment'] = 'Flavor "{0}" does not exist.'.format(name)
    else:
        if dry_run:
            ret['result'] = None
            ret['comment'] = 'Flavor "{0}", id: {1}  would be deleted.'.format(name, object_id)
            ret['changes'] = {name: {'old': 'Flavor "{0}", id: {1}  exists.'.format(name, object_id),
                                     'new': ret['comment']}}
        else:
            flavor_delete = __salt__['nova.flavor_delete'](object_id, **kwargs)

            if flavor_delete:
                ret['result'] = True
                ret['comment'] = 'Flavor "{0}", id: {1}  deleted.'.format(name, object_id)
                ret['changes'] = {name: {'old': 'Flavor "{0}", id: {1}  existed.'.format(name, object_id),
                                         'new': ret['comment']}}

    return ret
