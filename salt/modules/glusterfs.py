# -*- coding: utf-8 -*-
'''
Manage a glusterfs pool
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import 3rd-party libs
from salt.ext.six.moves import range, shlex_quote as _cmd_quote  # pylint: disable=import-error,redefined-builtin
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils
import salt.utils.cloud as suc

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the gluster command exists
    '''
    if salt.utils.which('gluster'):
        return True
    return False


def list_peers():
    '''
    Return a list of gluster peers

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.list_peers

    GLUSTER direct CLI example (to show what salt is sending to gluster):

        $ gluster peer status

    GLUSTER CLI 3.4.4 return example (so we know what we are parsing):

        Number of Peers: 2

        Hostname: ftp2
        Port: 24007
        Uuid: cbcb256b-e66e-4ec7-a718-21082d396c24
        State: Peer in Cluster (Connected)

        Hostname: ftp3
        Uuid: 5ea10457-6cb2-427b-a770-7897509625e9
        State: Peer in Cluster (Connected)


    '''
    get_peer_list = 'gluster peer status | awk \'/Hostname/ {print $2}\''
    result = __salt__['cmd.run'](get_peer_list, python_shell=True)
    if 'No peers present' in result:
        return None
    else:
        return result.splitlines()


def peer(name):
    '''
    Add another node into the peer list.

    name
        The remote host to probe.

    CLI Example:

    .. code-block:: bash

        salt 'one.gluster.*' glusterfs.peer two

    GLUSTER direct CLI example (to show what salt is sending to gluster):

        $ gluster peer probe ftp2

    GLUSTER CLI 3.4.4 return example (so we know what we are parsing):
        #if the "peer" is the local host:
        peer probe: success: on localhost not needed

        #if the peer was just added:
        peer probe: success

        #if the peer was already part of the cluster:
        peer probe: success: host ftp2 port 24007 already in peer list



    '''
    if suc.check_name(name, 'a-zA-Z0-9._-'):
        return 'Invalid characters in peer name'

    cmd = 'gluster peer probe {0}'.format(name)
    return __salt__['cmd.run'](cmd)


def create(name, bricks, stripe=False, replica=False, device_vg=False,
           transport='tcp', start=False):
    '''
    Create a glusterfs volume.

    name
        Name of the gluster volume

    bricks
        Bricks to create volume from, in <peer>:<brick path> format. For \
        multiple bricks use list format: '["<peer1>:<brick1>", \
        "<peer2>:<brick2>"]'

    stripe
        Stripe count, the number of bricks should be a multiple of the stripe \
        count for a distributed striped volume

    replica
        Replica count, the number of bricks should be a multiple of the \
        replica count for a distributed replicated volume

    device_vg
        If true, specifies volume should use block backend instead of regular \
        posix backend. Block device backend volume does not support multiple \
        bricks

    transport
        Transport protocol to use, can be 'tcp', 'rdma' or 'tcp,rdma'

    start
        Start the volume after creation

    CLI Example:

    .. code-block:: bash

        salt host1 glusterfs.create newvolume host1:/brick

        salt gluster1 glusterfs.create vol2 '["gluster1:/export/vol2/brick", \
        "gluster2:/export/vol2/brick"]' replica=2 start=True
    '''
    # If single brick given as a string, accept it
    if isinstance(bricks, str):
        bricks = [bricks]

    # Error for block devices with multiple bricks
    if device_vg and len(bricks) > 1:
        return 'Error: Block device backend volume does not support multipl' +\
            'bricks'

    # Validate bricks syntax
    for brick in bricks:
        try:
            peer_name, path = brick.split(':')
            if not path.startswith('/'):
                return 'Error: Brick paths must start with /'
        except ValueError:
            return 'Error: Brick syntax is <peer>:<path>'

    # Format creation call
    cmd = 'gluster volume create {0} '.format(name)
    if stripe:
        cmd += 'stripe {0} '.format(stripe)
    if replica:
        cmd += 'replica {0} '.format(replica)
    if device_vg:
        cmd += 'device vg '
    if transport != 'tcp':
        cmd += 'transport {0} '.format(transport)
    cmd += ' '.join(bricks)

    log.debug('Clustering command:\n{0}'.format(cmd))
    ret = __salt__['cmd.run'](cmd)
    if 'failed' in ret:
        return ret

    if start:
        result = __salt__['cmd.run']('gluster volume start {0}'.format(name))
        if result.endswith('success'):
            return 'Volume {0} created and started'.format(name)
        else:
            return result
    else:
        return 'Volume {0} created. Start volume to use'.format(name)


def list_volumes():
    '''
    List configured volumes

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.list_volumes
    '''

    results = __salt__['cmd.run']('gluster volume list').splitlines()
    if results[0] == 'No volumes present in cluster':
        return []
    else:
        return results


def status(name):
    '''
    Check the status of a gluster volume.

    name
        Volume name

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.status myvolume
    '''
    # Get volume status
    cmd = 'gluster volume status {0}'.format(name)
    result = __salt__['cmd.run'](cmd).splitlines()
    if 'does not exist' in result[0]:
        return result[0]
    if 'is not started' in result[0]:
        return result[0]

    ret = {'bricks': {}, 'nfs': {}, 'healers': {}}
    # Iterate line by line, concatenating lines the gluster cli separated
    for line_number in range(len(result)):
        line = result[line_number]
        if line.startswith('Brick'):
            # See if this line is broken up into multiple lines
            while len(line.split()) < 5:
                line_number = line_number + 1
                line = line.rstrip() + result[line_number]

            # Parse Brick data
            brick, port, online, pid = line.split()[1:]
            host, path = brick.split(':')
            data = {'port': port, 'pid': pid, 'host': host, 'path': path}
            if online == 'Y':
                data['online'] = True
            else:
                data['online'] = False
            # Store, keyed by <host>:<brick> string
            ret['bricks'][brick] = data
        elif line.startswith('NFS Server on'):
            # See if this line is broken up into multiple lines
            while len(line.split()) < 5:
                line_number = line_number + 1
                line = line.rstrip() + result[line_number]

            # Parse NFS Server data
            host, port, online, pid = line.split()[3:]
            data = {'port': port, 'pid': pid}
            if online == 'Y':
                data['online'] = True
            else:
                data['online'] = False
            # Store, keyed by hostname
            ret['nfs'][host] = data
        elif line.startswith('Self-heal Daemon on'):
            # See if this line is broken up into multiple lines
            while len(line.split()) < 5:
                line_number = line_number + 1
                line = line.rstrip() + result[line_number]

            # Parse NFS Server data
            host, port, online, pid = line.split()[3:]
            data = {'port': port, 'pid': pid}
            if online == 'Y':
                data['online'] = True
            else:
                data['online'] = False
            # Store, keyed by hostname
            ret['healers'][host] = data
    return ret


def start_volume(name):
    '''
    Start a gluster volume.

    name
        Volume name

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.start mycluster
    '''
    volumes = list_volumes()
    if name in volumes:
        if isinstance(status(name), dict):
            return 'Volume already started'
        cmd = 'gluster volume start {0}'.format(name)
        result = __salt__['cmd.run'](cmd)
        if result.endswith('success'):
            return 'Volume {0} started'.format(name)
        else:
            return result
    return 'Volume does not exist'


def stop_volume(name):
    '''
    Stop a gluster volume.

    name
        Volume name

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.stop_volume mycluster
    '''
    vol_status = status(name)
    if isinstance(vol_status, dict):
        cmd = 'yes | gluster volume stop {0}'.format(_cmd_quote(name))
        result = __salt__['cmd.run'](cmd, python_shell=True)
        if result.splitlines()[0].endswith('success'):
            return 'Volume {0} stopped'.format(name)
        else:
            return result
    return vol_status


def delete(target, stop=True):
    '''
    Deletes a gluster volume

    target
        Volume to delete

    stop
        Stop volume before delete if it is started, True by default
    '''
    if target not in list_volumes():
        return 'Volume does not exist'

    cmd = 'yes | gluster volume delete {0}'.format(_cmd_quote(target))

    # Stop volume if requested to and it is running
    if stop is True and isinstance(status(target), dict):
        stop_volume(target)
        stopped = True
    else:
        stopped = False
        # Warn volume is running if stop not requested
        if isinstance(status(target), dict):
            return 'Error: Volume must be stopped before deletion'

    result = __salt__['cmd.run'](cmd, python_shell=True)
    if result.splitlines()[0].endswith('success'):
        if stopped:
            return 'Volume {0} stopped and deleted'.format(target)
        else:
            return 'Volume {0} deleted'.format(target)
    else:
        return result


def add_volume_bricks(name, bricks):
    '''
    Add brick(s) to an existing volume

    name
        Volume name

    bricks
        List of bricks to add to the volume
    '''

    new_bricks = []

    cmd = 'echo yes | gluster volume add-brick {0}'.format(name)

    if isinstance(bricks, str):
        bricks = [bricks]

    volume_bricks = status(name)

    if 'does not exist' in volume_bricks:
        return volume_bricks

    if 'is not started' in volume_bricks:
        return volume_bricks

    for brick in bricks:
        if brick in volume_bricks['bricks']:
            log.debug('Brick {0} already in volume {1}...excluding from command'.format(brick, name))
        else:
            new_bricks.append(brick)

    if len(new_bricks) > 0:
        for brick in new_bricks:
            cmd += ' '+str(brick)

        result = __salt__['cmd.run'](cmd)

        if result.endswith('success'):
            return '{0} bricks successfully added to the volume {1}'.format(len(new_bricks), name)
        else:
            return result

    else:
        return 'Bricks already in volume {0}'.format(name)
