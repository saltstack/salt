# -*- coding: utf-8 -*-
'''
Manage glusterfs pool.
'''

# Import python libs
from __future__ import generators
from __future__ import absolute_import
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

    .. code-block:: yaml

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

    if peers:
        if name in peers:
            ret['result'] = True
            ret['comment'] = 'Host {0} already peered'.format(name)
            return ret
        elif __opts__['test']:
            ret['comment'] = 'Peer {0} will be added.'.format(name)
            ret['result'] = None
            return ret

    if suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in peer name.'
        ret['result'] = False
        return ret

    if 'output' in __salt__['glusterfs.peer'](name):
        ret['comment'] = __salt__['glusterfs.peer'](name)['output']
    else:
        ret['comment'] = ''

    newpeers = __salt__['glusterfs.list_peers']()
    #if newpeers was null, we know something didn't work.
    if newpeers and name in newpeers:
        ret['result'] = True
        ret['changes'] = {'new': newpeers, 'old': peers}
    #In case the hostname doesn't have any periods in it
    elif name == socket.gethostname():
        ret['result'] = True
        return ret
    #In case they have a hostname like "example.com"
    elif name == socket.gethostname().split('.')[0]:
        ret['result'] = True
        return ret
    elif 'on localhost not needed' in ret['comment']:
        ret['result'] = True
        ret['comment'] = 'Peering with localhost is not needed'
    else:
        ret['result'] = False
    return ret


def created(name, bricks, stripe=False, replica=False, device_vg=False,
            transport='tcp', start=False, force=False):
    '''
    Check if volume already exists

    name
        name of the volume

    .. code-block:: yaml

        myvolume:
          glusterfs.created:
            - bricks:
                - host1:/srv/gluster/drive1
                - host2:/srv/gluster/drive2

        Replicated Volume:
          glusterfs.created:
            - name: volume2
            - bricks:
              - host1:/srv/gluster/drive2
              - host2:/srv/gluster/drive3
            - replica: 2
            - start: True
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    volumes = __salt__['glusterfs.list_volumes']()
    if name in volumes:
        if start:
            if isinstance(__salt__['glusterfs.status'](name), dict):
                ret['result'] = True
                cmnt = 'Volume {0} already exists and is started.'.format(name)
            else:
                result = __salt__['glusterfs.start_volume'](name)
                if 'started' in result:
                    ret['result'] = True
                    cmnt = 'Volume {0} started.'.format(name)
                    ret['changes'] = {'new': 'started', 'old': 'stopped'}
                else:
                    ret['result'] = False
                    cmnt = result
        else:
            ret['result'] = True
            cmnt = 'Volume {0} already exists.'.format(name)
        ret['comment'] = cmnt
        return ret
    elif __opts__['test']:
        if start and isinstance(__salt__['glusterfs.status'](name), dict):
            comment = 'Volume {0} will be created and started'.format(name)
        else:
            comment = 'Volume {0} will be created'.format(name)
        ret['comment'] = comment
        ret['result'] = None
        return ret

    if suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in volume name.'
        ret['result'] = False
        return ret

    ret['comment'] = __salt__['glusterfs.create'](name, bricks, stripe,
                                                  replica, device_vg,
                                                  transport, start, force)

    old_volumes = volumes
    volumes = __salt__['glusterfs.list_volumes']()
    if name in volumes:
        ret['changes'] = {'new': volumes, 'old': old_volumes}
        ret['result'] = True

    return ret


def started(name):
    '''
    Check if volume has been started

    name
        name of the volume

    .. code-block:: yaml

        mycluster:
          glusterfs.started: []
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}
    volumes = __salt__['glusterfs.list_volumes']()
    if name not in volumes:
        ret['result'] = False
        ret['comment'] = 'Volume {0} does not exist'.format(name)
        return ret

    if isinstance(__salt__['glusterfs.status'](name), dict):
        ret['comment'] = 'Volume {0} is already started'.format(name)
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be started'.format(name)
        ret['result'] = None
        return ret

    ret['comment'] = __salt__['glusterfs.start_volume'](name)
    if 'started' in ret['comment']:
        ret['result'] = True
        ret['change'] = {'new': 'started', 'old': 'stopped'}
    else:
        ret['result'] = False

    return ret


def add_volume_bricks(name, bricks):
    '''
    Add brick(s) to an existing volume

    name
        Volume name

    bricks
        List of bricks to add to the volume

    .. code-block:: yaml

        myvolume:
          glusterfs.add_volume_bricks:
            - bricks:
                - host1:/srv/gluster/drive1
                - host2:/srv/gluster/drive2

        Replicated Volume:
          glusterfs.add_volume_bricks:
            - name: volume2
            - bricks:
              - host1:/srv/gluster/drive2
              - host2:/srv/gluster/drive3
    '''
    ret = {'name': name,
       'changes': {},
       'comment': '',
       'result': False}

    current_bricks = __salt__['glusterfs.status'](name)

    if 'does not exist' in current_bricks:
        ret['result'] = False
        ret['comment'] = current_bricks
        return ret

    if 'is not started' in current_bricks:
        ret['result'] = False
        ret['comment'] = current_bricks
        return ret

    add_bricks = __salt__['glusterfs.add_volume_bricks'](name, bricks)
    ret['comment'] = add_bricks

    if 'bricks successfully added' in add_bricks:
        old_bricks = current_bricks
        new_bricks = __salt__['glusterfs.status'](name)
        ret['result'] = True
        ret['changes'] = {'new': list(new_bricks['bricks'].keys()), 'old': list(old_bricks['bricks'].keys())}
        return ret

    if 'Bricks already in volume' in add_bricks:
        ret['result'] = True
        return ret

    return ret
