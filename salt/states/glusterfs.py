# -*- coding: utf-8 -*-
'''
Manage GlusterFS pool.
'''

# Import python libs
from __future__ import generators
from __future__ import absolute_import
import logging
import socket

# Import salt libs
import salt.utils
import salt.utils.cloud as suc
from salt.exceptions import SaltCloudException

log = logging.getLogger(__name__)

RESULT_CODES = [
    'Peer {0} added successfully.',
    'Probe on localhost not needed',
    'Host {0} is already in the peer group',
    'Host {0} is already part of another cluster',
    'Volume on {0} conflicts with existing volumes',
    'UUID of {0} is the same as local uuid',
    '{0} responded with "unknown peer". This could happen if {0} doesn\'t have localhost defined',
    'Failed to add peer. Information on {0}\'s logs',
    'Cluster quorum is not met. Changing peers is not allowed.',
    'Failed to update list of missed snapshots from {0}',
    'Conflict comparing list of snapshots from {0}',
    'Peer is already being detached from cluster.']


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

    try:
        suc.check_name(name, 'a-zA-Z0-9._-')
    except SaltCloudException as e:
        ret['comment'] = 'Invalid characters in peer name.'
        return ret

    # Check if the name resolves to localhost
    if socket.gethostbyname(name) in __salt__['network.ip_addrs']():
        ret['result'] = True
        ret['comment'] = 'Peering with localhost is not needed'
        return ret

    peers = __salt__['glusterfs.peer_status']()

    if peers and any(name in v['hostnames'] for v in peers.values()):
        ret['result'] = True
        ret['comment'] = 'Host {0} already peered'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Peer {0} will be added.'.format(name)
        ret['result'] = None
        return ret

    peered = __salt__['glusterfs.peer'](name)
    if not peered:
        ret['comment'] = 'Failed to peer with {0}, please check logs for errors'.format(name)
        return ret

    # Double check that the action succeeded
    newpeers = __salt__['glusterfs.peer_status']()
    if newpeers and any(name in v['hostnames'] for v in newpeers.values()):
        ret['result'] = True
        ret['comment'] = 'Host {0} successfully peered'.format(name)
        ret['changes'] = {'new': newpeers, 'old': peers}
    else:
        ret['comment'] = 'Host {0} was successfully peered but did not appear in the list of peers'.format(name)
    return ret


def volume_present(name, bricks, stripe=False, replica=False, device_vg=False,
            transport='tcp', start=False, force=False):
    '''
    Ensure that the volume exists

    name
        name of the volume

    bricks
        list of brick paths

    start
        ensure that the volume is also started

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

    if suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in volume name.'
        return ret

    volumes = __salt__['glusterfs.list_volumes']()
    if name not in volumes:
        if __opts__['test']:
            comment = 'Volume {0} will be created'.format(name)
            if start:
                comment += ' and started'
            ret['comment'] = comment
            ret['result'] = None
            return ret

        vol_created = __salt__['glusterfs.create_volume'](name, bricks, stripe,
                                                  replica, device_vg,
                                                  transport, start, force)

        if not vol_created:
            ret['comment'] = 'Creation of volume {0} failed'.format(name)
            return ret
        old_volumes = volumes
        volumes = __salt__['glusterfs.list_volumes']()
        if name in volumes:
            ret['changes'] = {'new': volumes, 'old': old_volumes}
            ret['comment'] = 'Volume {0} is created'.format(name)

    else:
        ret['comment'] = 'Volume {0} already exists'.format(name)

    if start:
        if __opts__['test']:
            # volume already exists
            ret['comment'] = ret['comment'] + ' and will be started'
            ret['result'] = None
            return ret
        if int(__salt__['glusterfs.info']()[name]['status']) == 1:
            ret['result'] = True
            ret['comment'] = ret['comment'] + ' and is started'
        else:
            vol_started = __salt__['glusterfs.start_volume'](name)
            if vol_started:
                ret['result'] = True
                ret['comment'] = ret['comment'] + ' and is now started'
                if not ret['changes']:
                    ret['changes'] = {'new': 'started', 'old': 'stopped'}
            else:
                ret['comment'] = ret['comment'] + ' but failed to start. Check logs for further information'
                return ret

    if __opts__['test']:
        ret['result'] = None
    else:
        ret['result'] = True
    return ret


def created(*args, **kwargs):
    '''
    Deprecated version of more descriptively named volume_present
    '''
    salt.utils.warn_until(
        'Nitrogen',
        'The glusterfs.created state is deprecated in favor of more descriptive'
        ' glusterfs.volume_present.'
    )
    return volume_present(*args, **kwargs)


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

    volinfo = __salt__['glusterfs.info']()
    if name not in volinfo:
        ret['result'] = False
        ret['comment'] = 'Volume {0} does not exist'.format(name)
        return ret

    if int(volinfo[name]['status']) == 1:
        ret['comment'] = 'Volume {0} is already started'.format(name)
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be started'.format(name)
        ret['result'] = None
        return ret

    vol_started = __salt__['glusterfs.start_volume'](name)
    if vol_started:
        ret['result'] = True
        ret['comment'] = 'Volume {0} is started'.format(name)
        ret['change'] = {'new': 'started', 'old': 'stopped'}
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to start volume {0}'.format(name)

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

    volinfo = __salt__['glusterfs.info']()
    if name not in volinfo:
        ret['comment'] = 'Volume {0} does not exist'.format(name)
        return ret

    if int(volinfo[name]['status']) != 1:
        ret['comment'] = 'Volume {0} is not started'.format(name)
        return ret

    current_bricks = [brick['path'] for brick in volinfo[name]['bricks'].values()]
    if not set(bricks) - set(current_bricks):
        ret['result'] = True
        ret['comment'] = 'Bricks already added in volume {0}'.format(name)
        return ret

    bricks_added = __salt__['glusterfs.add_volume_bricks'](name, bricks)
    if bricks_added:
        ret['result'] = True
        ret['comment'] = 'Bricks successfully added to volume {0}'.format(name)
        new_bricks = [brick['path'] for brick in __salt__['glusterfs.info']()[name]['bricks'].values()]
        ret['changes'] = {'new': new_bricks, 'old': current_bricks}
        return ret

    ret['comment'] = 'Adding bricks to volume {0} failed'.format(name)
    return ret
