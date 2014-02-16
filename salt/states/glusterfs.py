# -*- coding: utf-8 -*-
'''
Manage glusterfs pool.
'''

# Import python libs
from __future__ import generators
import logging
import socket

# Import salt libs
import salt.utils.cloud as suc

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the gluster command exists
    '''
    return 'glusterfs' if 'glusterfs.list_volumes' in __salt__ else False


def peered(name):
    '''
    Check if node is peered.

    name
        The remote host with which to peer.

    peer-cluster:
      glusterfs.peered:
        - name: two

    peer-clusters:
      glusterfs.peered:
        - names:
          - one
          - two
          - three
          - four
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
        ret['result'] = None
        return ret

    if not suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in peer name.'
        ret['result'] = False
        return ret

    ret['comment'] = __salt__['glusterfs.peer'](name)

    newpeers = __salt__['glusterfs.list_peers']()
    if name in newpeers:
        ret['result'] = True
        ret['changes'] = {'new': newpeers, 'old': peers}
    elif name == socket.gethostname().split('.')[0]:
        ret['result'] = True
        return ret
    else:
        ret['result'] = False
    return ret


def created(name, peers=None, **kwargs):
    '''
    Check if volume already exists

    name
        name of the volume

    gluster-cluster:
      glusterfs.created:
        - name: mycluster
        - brick: /srv/gluster/drive1
        - replica: True
        - count: 2
        - short: True
        - start: True
        - peers:
          - one
          - two
          - three
          - four
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
        ret['result'] = None
        return ret

    if not suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in volume name.'
        ret['result'] = False
        return ret

    if not all([suc.check_name(peer, 'a-zA-Z0-9._-') for peer in peers]):
        ret['comment'] = 'Invalid characters in a peer name.'
        ret['result'] = False
        return ret

    ret['comment'] = __salt__['glusterfs.create'](name, peers, **kwargs)

    if name in __salt__['glusterfs.list_volumes']():
        ret['changes'] = {'new': name, 'old': ''}
        ret['result'] = True

    return ret


def started(name, **kwargs):
    '''
    Check if volume has been started

    name
        name of the volume
    gluster-started:
      glusterfs.started:
        - name: mycluster
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

    if not suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in volume name.'
        ret['result'] = False
        return ret
    status = __salt__['glusterfs.status'](name)

    if status != 'Volume {0} is not started'.format(name):
        ret['comment'] = status
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be created'.format(name)
        ret['result'] = None
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
