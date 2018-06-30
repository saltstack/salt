# -*- coding: utf-8 -*-
'''
Management of OpenStack Keystone Domains
========================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.keystoneng` for setup instructions

Example States

.. code-block:: yaml

    create domain:
      keystone_domain.present:
        - name: domain1

    create domain with optional params:
      keystone_domain.present:
        - name: domain1
        - enabled: False
        - description: 'my domain'

    delete domain:
      keystone_domain.absent:
        - name: domain1
'''

from __future__ import absolute_import, unicode_literals, print_function

__virtualname__ = 'keystone_domain'


def __virtual__():
    if 'keystoneng.domain_get' in __salt__:
        return __virtualname__
    return (False, 'The keystoneng execution module failed to load: shade python module is not available')


def present(name, auth=None, **kwargs):
    '''
    Ensure domain exists and is up-to-date

    name
        Name of the domain

    enabled
        Boolean to control if domain is enabled

    description
        An arbitrary description of the domain
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    domain = __salt__['keystoneng.domain_get'](name=name)

    if not domain:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = kwargs
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Domain {} will be created.'.format(name)
            return ret

        kwargs['name'] = name
        domain = __salt__['keystoneng.domain_create'](**kwargs)
        ret['changes'] = domain
        ret['comment'] = 'Created domain'
        return ret

    changes = __salt__['keystoneng.compare_changes'](domain, **kwargs)
    if changes:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = changes
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Domain {} will be updated.'.format(name)
            return ret

        kwargs['domain_id'] = domain.id
        __salt__['keystoneng.domain_update'](**kwargs)
        ret['changes'].update(changes)
        ret['comment'] = 'Updated domain'

    return ret


def absent(name, auth=None):
    '''
    Ensure domain does not exist

    name
        Name of the domain
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    __salt__['keystoneng.setup_clouds'](auth)

    domain = __salt__['keystoneng.domain_get'](name=name)

    if domain:
        if __opts__['test'] is True:
            ret['result'] = None
            ret['changes'] = {'name': name}
            ret['pchanges'] = ret['changes']
            ret['comment'] = 'Domain {} will be deleted.'.format(name)
            return ret

        __salt__['keystoneng.domain_delete'](name=domain)
        ret['changes']['id'] = domain.id
        ret['comment'] = 'Deleted domain'

    return ret
