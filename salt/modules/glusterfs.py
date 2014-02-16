# -*- coding: utf-8 -*-
'''
Manage glusterfs pool.
'''

# Import python libs
from __future__ import generators
import logging
import os.path
import socket

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


def list_peers():
    '''
    Return a list of gluster peers

    salt '*' glusterfs.list_peers
    '''
    get_peer_list = 'gluster peer status | awk \'/Hostname/ {print $2}\''
    return __salt__['cmd.run'](get_peer_list).splitlines()


def peer(name=None, **kwargs):
    '''
    Add another node into the peer probe.
    That node must be referenced in /etc/hosts.

    Need to add the ability to add to use ip addresses

    name
        The remote host with which to peer.

    names
        List of hosts with which to peer.

    If names is specified, name will be ignored.

    salt 'one.gluster.*' glusterfs.peer two
    '''
    hosts_file = __salt__['hosts.list_hosts']()
    hosts_list = []
    for ip, hosts in hosts_file.items():
        hosts_list.extend(hosts)
    if name in hosts_list:
        cmd = 'gluster peer probe {0}'.format(name)
        return __salt__['cmd.run'](cmd)
    return 'Node not referenced in /etc/hosts.'


def create(name,
           peers=None,
           brick='/srv/gluster/brick1',
           replica=False,
           count=2,
           **kwargs):
    '''
    Create a glusterfs volume.

    name
        name of the gluster volume

    brick
        filesystem path for the brick

    peers
        peers that will be part of the cluster

    replica
        replicated or distributed cluster

    count
        number of nodes per replica block

    short
        (optional) use short names for peering

    salt 'one.gluster*' glusterfs.create mymount /srv/ peers='["one", "two"]'

    salt -G 'gluster:master' glusterfs.create mymount /srv/gluster/brick1 \
        peers='["one", "two", "three", "four"]' replica=True count=2 \
        short=True start=True
    '''
    check_peers = 'gluster peer status | awk \'/Hostname/ {print $2}\''
    active_peers = __salt__['cmd.run'](check_peers).splitlines()
    hostname = socket.gethostname()
    if 'short' in kwargs and kwargs['short']:
        hostname = hostname.split('.')[0]
    if not all([peer in active_peers for peer in peers if peer != hostname]):
        return 'Not all peers have been probed.'

    if not os.path.exists(brick):
        return 'Brick path doesn\'t exist.'

    cmd = 'gluster volume create {0} '.format(name)
    if replica:
        cmd += 'replica {0} '.format(count)
    for peer in peers:
        cmd += '{0}:{1} '.format(peer, brick)

    log.debug('Clustering command:\n{0}'.format(cmd))
    ret = __salt__['cmd.run'](cmd)

    if 'start' in kwargs and kwargs['start']:
        ret = __salt__['cmd.run']('gluster volume start {0}'.format(name))

    return ret


def list_volumes():
    return __salt__['cmd.run']('gluster volume list').splitlines()


def status(name):
    '''
    Check the status of a gluster volume.

    name
        Volume name
    '''
    volumes = list_volumes()
    if name in volumes:
        cmd = 'gluster volume status {0}'.format(name)
        return __salt__['cmd.run'](cmd)
    return 'Volume {0} doesn\'t exist'.format(name)


def start(name):
    '''
    Start a gluster volume.

    name
        Volume name
    '''
    volumes = list_volumes()
    if name in volumes:
        cmd = 'gluster volume start {0}'.format(name)
        return __salt__['cmd.run'](cmd)
    return False
