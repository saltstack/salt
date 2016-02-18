# -*- coding: utf-8 -*-
'''
Manage a glusterfs pool
'''
from __future__ import absolute_import

# Import python libs
import logging
import sys
import xml.etree.ElementTree as ET

# Import 3rd-party libs
# pylint: disable=import-error,redefined-builtin
from salt.ext.six.moves import range
# pylint: enable=import-error,redefined-builtin

# Import salt libs
import salt.utils
import salt.utils.cloud as suc
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the gluster command exists
    '''
    if salt.utils.which('gluster'):
        return True
    return (False, 'glusterfs server is not installed')


def _get_minor_version():
    # Set default version to 6 for tests
    version = 6
    cmd = 'gluster --version'
    result = __salt__['cmd.run'](cmd).splitlines()
    for line_number in range(len(result)):
        line = result[line_number]
        if line.startswith('glusterfs'):
            version = int(line.split()[1].split('.')[1])
    return version


def _gluster(cmd):
    '''
    Perform a gluster command.
    '''
    # We will pass the command string as stdin to allow for much longer
    # command strings. This is especially useful for creating large volumes
    # where the list of bricks exceeds 128 characters.
    return __salt__['cmd.run'](
        'gluster --mode=script', stdin="{0}\n".format(cmd))


def _gluster_xml(cmd):
    '''
    Perform a gluster --xml command and check for and raise errors.
    '''
    root = ET.fromstring(
        __salt__['cmd.run'](
            'gluster --xml --mode=script', stdin="{0}\n".format(cmd)
        ).replace("\n", ""))
    if int(root.find('opRet').text) != 0:
        raise CommandExecutionError(root.find('opErrstr').text)
    return root


def _etree_to_dict(t):
    list_t = list(t)
    if len(list_t) > 0:
        d = {}
        for child in list_t:
            d[child.tag] = _etree_to_dict(child)
    else:
        d = t.text
    return d


def _iter(root, term):
    '''
    Checks for python2.6 or python2.7
    '''
    if sys.version_info < (2, 7):
        return root.getiterator(term)
    else:
        return root.iter(term)


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
    root = _gluster_xml('peer status')
    result = {}
    for et_peer in _iter(root, 'peer'):
        result.update({et_peer.find('hostname').text: [
                      x.text for x in _iter(et_peer.find('hostnames'), 'hostname')]})
    if len(result) == 0:
        return None
    else:
        return result


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
        raise SaltInvocationError(
            'Invalid characters in peer name "{0}"'.format(name))

    cmd = 'peer probe {0}'.format(name)

    op_result = {
        "exitval": _gluster_xml(cmd).find('opErrno').text,
        "output": _gluster_xml(cmd).find('output').text
    }
    return op_result


def create(name, bricks, stripe=False, replica=False, device_vg=False,
           transport='tcp', start=False, force=False):
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

    force
        Force volume creation, this works even if creating in root FS

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
        raise SaltInvocationError('Block device backend volume does not ' +
                                  'support multiple bricks')

    # Validate bricks syntax
    for brick in bricks:
        try:
            peer_name, path = brick.split(':')
            if not path.startswith('/'):
                raise SaltInvocationError(
                    'Brick paths must start with / in {0}'.format(brick))
        except ValueError:
            raise SaltInvocationError(
                'Brick syntax is <peer>:<path> got {0}'.format(brick))

    # Format creation call
    cmd = 'volume create {0} '.format(name)
    if stripe:
        cmd += 'stripe {0} '.format(stripe)
    if replica:
        cmd += 'replica {0} '.format(replica)
    if device_vg:
        cmd += 'device vg '
    if transport != 'tcp':
        cmd += 'transport {0} '.format(transport)
    cmd += ' '.join(bricks)
    if force:
        cmd += ' force'

    log.debug('Clustering command:\n{0}'.format(cmd))
    _gluster_xml(cmd)

    if start:
        _gluster_xml('volume start {0}'.format(name))
        return 'Volume {0} created and started'.format(name)
    else:
        return 'Volume {0} created. Start volume to use'.format(name)


def list_volumes():
    '''
    List configured volumes

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.list_volumes
    '''

    get_volume_list = 'gluster --xml volume list'
    root = _gluster_xml('volume list')
    results = [x.text for x in _iter(root, 'volume')]
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
    root = _gluster_xml('volume status {0}'.format(name))

    ret = {'bricks': {}, 'nfs': {}, 'healers': {}}

    def etree_legacy_wrap(t):
        ret = _etree_to_dict(t)
        ret['online'] = (ret['status'] == '1')
        ret['host'] = ret['hostname']
        return ret

    # Build a hash to map hostname to peerid
    hostref = {}
    for node in _iter(root, 'node'):
        peerid = node.find('peerid').text
        hostname = node.find('hostname').text
        if hostname not in ('NFS Server', 'Self-heal Daemon'):
            hostref[peerid] = hostname

    for node in _iter(root, 'node'):
        hostname = node.find('hostname').text
        if hostname not in ('NFS Server', 'Self-heal Daemon'):
            path = node.find('path').text
            ret['bricks'][
                '{0}:{1}'.format(hostname, path)] = etree_legacy_wrap(node)
        elif hostname == 'NFS Server':
            peerid = node.find('peerid').text
            true_hostname = hostref[peerid]
            ret['nfs'][true_hostname] = etree_legacy_wrap(node)
        else:
            peerid = node.find('peerid').text
            true_hostname = hostref[peerid]
            ret['healers'][true_hostname] = etree_legacy_wrap(node)

    return ret


def info(name):
    '''
    .. versionadded:: 2015.8.4

    Return the gluster volume info.

    name
        Volume name

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.info myvolume

    '''
    cmd = 'volume info {0}'.format(name)
    root = _gluster_xml(cmd)

    volume = [x for x in _iter(root, 'volume')][0]

    ret = {name: _etree_to_dict(volume)}

    bricks = {}
    for i, brick in enumerate(_iter(volume, 'brick'), start=1):
        brickkey = 'brick{0}'.format(i)
        bricks[brickkey] = {'path': brick.text}
        for child in list(brick):
            if not child.tag == 'name':
                bricks[brickkey].update({child.tag: child.text})
        for k, v in brick.items():
            bricks[brickkey][k] = v
    ret[name]['bricks'] = bricks

    options = {}
    for option in _iter(volume, 'option'):
        options[option.find('name').text] = option.find('value').text
    ret[name]['options'] = options

    return ret


def start_volume(name, force=False):
    '''
    Start a gluster volume.

    name
        Volume name

    force
        Force the volume start even if the volume is started
        .. versionadded:: 2015.8.4

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.start mycluster
    '''
    cmd = 'volume start {0}'.format(name)
    if force:
        cmd = '{0} force'.format(cmd)

    volinfo = info(name)

    if not force and volinfo['status'] == '1':
        return 'Volume already started'

    _gluster_xml(cmd)
    return 'Volume {0} started'.format(name)


def stop_volume(name, force=False):
    '''
    Stop a gluster volume.

    name
        Volume name

    force
        Force stop the volume
        .. versionadded:: 2015.8.4

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.stop_volume mycluster
    '''
    status(name)

    cmd = 'volume stop {0}'.format(name)
    if force:
        cmd += ' force'

    _gluster_xml(cmd)
    return 'Volume {0} stopped'.format(name)


def delete(target, stop=True):
    '''
    Deletes a gluster volume

    target
        Volume to delete

    stop
        Stop volume before delete if it is started, True by default
    '''
    if target not in list_volumes():
        raise SaltInvocationError('Volume {0} does not exist'.format(target))

    # Stop volume if requested to and it is running
    running = (info(target)['status'] == '1')

    if not stop and running:
        # Fail if volume is running if stop is not requested
        raise SaltInvocationError(
            'Volume {0} must be stopped before deletion'.format(target))

    if running:
        stop_volume(target, force=True)

    cmd = 'volume delete {0}'.format(target)
    _gluster_xml(cmd)
    if running:
        return 'Volume {0} stopped and deleted'.format(target)
    else:
        return 'Volume {0} deleted'.format(target)


def add_volume_bricks(name, bricks):
    '''
    Add brick(s) to an existing volume

    name
        Volume name

    bricks
        List of bricks to add to the volume
    '''

    new_bricks = []

    cmd = 'volume add-brick {0}'.format(name)

    if isinstance(bricks, str):
        bricks = [bricks]

    volume_bricks = [x['path'] for x in info(name)['bricks'].values()]

    for brick in bricks:
        if brick in volume_bricks:
            log.debug(
                'Brick {0} already in volume {1}...excluding from command'.format(brick, name))
        else:
            new_bricks.append(brick)

    if len(new_bricks) > 0:
        for brick in new_bricks:
            cmd += ' {0}'.format(brick)

        _gluster_xml(cmd)

        return '{0} bricks successfully added to the volume {1}'.format(len(new_bricks), name)

    else:
        return 'Bricks already in volume {0}'.format(name)
