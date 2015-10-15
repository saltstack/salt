# -*- coding: utf-8 -*-
'''
Manage Rackspace Queues
=======================

.. versionadded:: 2015.5.0

Create and destroy Rackspace queues. Be aware that this interacts with
Rackspace's services, and so may incur charges.

This module uses ``pyrax``, which can be installed via package, or pip.
This module is greatly inspired by boto_* modules from SaltStack code source.

.. code-block:: yaml

    myqueue:
        pyrax_queues.present:
            - provider: my-pyrax

    myqueue:
        pyrax_queues.absent:
            - provider: my-pyrax
'''
from __future__ import absolute_import

import salt.utils.openstack.pyrax as suop


def __virtual__():
    '''
    Only load if pyrax is available.
    '''
    return suop.HAS_PYRAX


def present(name, provider):
    '''
    Ensure the RackSpace queue exists.

    name
        Name of the Rackspace queue.

    provider
        Salt Cloud Provider
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = list(__salt__['cloud.action']('queues_exists', provider=provider, name=name)[provider].values())[0]

    if not is_present:
        if __opts__['test']:
            msg = 'Rackspace queue {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        created = __salt__['cloud.action']('queues_create', provider=provider, name=name)
        if created:
            queue = __salt__['cloud.action']('queues_show', provider=provider, name=name)
            ret['changes']['old'] = {}
            ret['changes']['new'] = {'queue': queue}
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} Rackspace queue.'.format(name)
            return ret
    else:
        ret['comment'] = '{0} present.'.format(name)

    return ret


def absent(name, provider):
    '''
    Ensure the named Rackspace queue is deleted.

    name
        Name of the Rackspace queue.

    provider
        Salt Cloud provider
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = list(__salt__['cloud.action']('queues_exists', provider=provider, name=name)[provider].values())[0]

    if is_present:
        if __opts__['test']:
            ret['comment'] = 'Rackspace queue {0} is set to be removed.'.format(
                name)
            ret['result'] = None
            return ret
        queue = __salt__['cloud.action']('queues_show', provider=provider, name=name)
        deleted = __salt__['cloud.action']('queues_delete', provider=provider, name=name)
        if deleted:
            ret['changes']['old'] = queue
            ret['changes']['new'] = {}
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} Rackspace queue.'.format(name)
    else:
        ret['comment'] = '{0} does not exist.'.format(name)

    return ret
