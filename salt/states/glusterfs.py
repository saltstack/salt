# -*- coding: utf-8 -*-
'''
Manage glusterfs pool.
'''

# Import python libs
from __future__ import generators
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the gluster command exists
    '''
    if salt.utils.which('gluster'):
        return True
    else:
        return False


def peered(name):
    '''
    Check if node is peered.
    Must be a hostname stored in /etc/hosts.

    name
        The remote host with which to peer.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}

    peers = __salt__['glusterfs.list_peers']()

    if name in peers:
        ret['result'] = True
        ret['comment'] = 'Host {0} already peered'.format(name)
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Peer {0} will be added.'.format(name)
        ret['result'] = True
        return ret

    ret['comment'] = __salt__['glusterfs.peer'](name)

    newpeers = __salt__['glusterfs.list_peers']()
    if name in peers:
        ret['result'] = True
        ret['change'] = {'new': newpeers, 'old': peers}
    else:
        ret['result'] = False
    return ret


def created(name, **kwargs):
    '''
    Check if volume already exists

    name
        name of the volume
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    volumes = __salt__['glusterfs.list_volumes']()
    if name in volumes:
        ret['result'] = True
        ret['comment'] = 'Volume {0} already exists.'.format(name)
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be created'.format(name)
        ret['result'] = True
        return ret

    ret['comment'] = __salt__['glusterfs.create'](name, kwargs)

    if name in __salt__['glusterfs.list_volumes']():
        ret['changes'] = {'new': name, 'old': ''}
        ret['result'] = True

    return ret


def started(name, **kwargs):
    '''
    Check if volume has been started

    name
        name of the volume
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    volumes = __salt__['glusterfs.list_volumes']()
    if not name in volumes:
        ret['result'] = False
        ret['comment'] = 'Volume {0} does not exist'.format(name)
        return ret

    status = __salt__['glusterfs.status'](name)

    if status != 'Volume {0} is not started'.format(name):
        ret['comment'] = status
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be created'.format(name)
        ret['result'] = True
        return ret

    ret['comment'] = __salt__['glusterfs.start'](name)
    ret['result'] = True

    status = __salt__['glusterfs.status'](name)
    if status == 'Volume {0} is not started'.format(name):
        ret['comment'] = status
        ret['result'] = False
        return ret

    ret['change'] = {'new': 'started', 'old': ''}
    return ret
