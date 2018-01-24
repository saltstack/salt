# -*- coding: utf-8 -*-
'''
Manage a glusterfs pool
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import logging
import sys
import xml.etree.ElementTree as ET

# Import salt libs
import salt.utils.cloud
import salt.utils.path
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the gluster command exists
    '''
    if salt.utils.path.which('gluster'):
        return True
    return (False, 'glusterfs server is not installed')


def _get_minor_version():
    # Set default version to 6 for tests
    version = 6
    cmd = 'gluster --version'
    result = __salt__['cmd.run'](cmd).splitlines()
    for line in result:
        if line.startswith('glusterfs'):
            version = int(line.split()[1].split('.')[1])
    return version


def _gluster_ok(xml_data):
    '''
    Extract boolean return value from Gluster's XML output.
    '''
    return int(xml_data.find('opRet').text) == 0


def _gluster_output_cleanup(result):
    '''
    Gluster versions prior to 6 have a bug that requires tricking
    isatty. This adds "gluster> " to the output. Strip it off and
    produce clean xml for ElementTree.
    '''
    ret = ''
    for line in result.splitlines():
        if line.startswith('gluster>'):
            ret += line[9:].strip()
        else:
            ret += line.strip()

    return ret


def _gluster_xml(cmd):
    '''
    Perform a gluster --xml command and log result.
    '''
    # We will pass the command string as stdin to allow for much longer
    # command strings. This is especially useful for creating large volumes
    # where the list of bricks exceeds 128 characters.
    if _get_minor_version() < 6:
        result = __salt__['cmd.run'](
            'script -q -c "gluster --xml --mode=script"', stdin="{0}\n\004".format(cmd)
        )
    else:
        result = __salt__['cmd.run'](
            'gluster --xml --mode=script', stdin="{0}\n".format(cmd)
        )

    try:
        root = ET.fromstring(_gluster_output_cleanup(result))
    except ET.ParseError:
        raise CommandExecutionError('\n'.join(result.splitlines()[:-1]))

    if _gluster_ok(root):
        output = root.find('output')
        if output is not None:
            log.info('Gluster call "%s" succeeded: %s',
                     cmd,
                     root.find('output').text)
        else:
            log.info('Gluster call "%s" succeeded', cmd)
    else:
        log.error('Failed gluster call: %s: %s',
                  cmd,
                  root.find('opErrstr').text)

    return root


def _gluster(cmd):
    '''
    Perform a gluster command and return a boolean status.
    '''
    return _gluster_ok(_gluster_xml(cmd))


def _etree_to_dict(t):
    d = {}
    for child in t:
        d[child.tag] = _etree_to_dict(child)
    return d or t.text


def _iter(root, term):
    '''
    Checks for python2.6 or python2.7
    '''
    if sys.version_info < (2, 7):
        return root.getiterator(term)
    else:
        return root.iter(term)


def peer_status():
    '''
    Return peer status information

    The return value is a dictionary with peer UUIDs as keys and dicts of peer
    information as values. Hostnames are listed in one list. GlusterFS separates
    one of the hostnames but the only reason for this seems to be which hostname
    happens to be used firts in peering.

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.peer_status

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
    if not _gluster_ok(root):
        return None

    result = {}
    for peer in _iter(root, 'peer'):
        uuid = peer.find('uuid').text
        result[uuid] = {'hostnames': []}
        for item in peer:
            if item.tag == 'hostname':
                result[uuid]['hostnames'].append(item.text)
            elif item.tag == 'hostnames':
                for hostname in item:
                    if hostname.text not in result[uuid]['hostnames']:
                        result[uuid]['hostnames'].append(hostname.text)
            elif item.tag != 'uuid':
                result[uuid][item.tag] = item.text
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
    if salt.utils.cloud.check_name(name, 'a-zA-Z0-9._-'):
        raise SaltInvocationError(
            'Invalid characters in peer name "{0}"'.format(name))

    cmd = 'peer probe {0}'.format(name)
    return _gluster(cmd)


def create_volume(name, bricks, stripe=False, replica=False, device_vg=False,
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
    if isinstance(bricks, six.string_types):
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

    if not _gluster(cmd):
        return False

    if start:
        return start_volume(name)
    return True


def list_volumes():
    '''
    List configured volumes

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.list_volumes
    '''

    root = _gluster_xml('volume list')
    if not _gluster_ok(root):
        return None
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
    if not _gluster_ok(root):
        # Most probably non-existing volume, the error output is logged
        # Tiis return value is easy to test and intuitive
        return None

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


def info(name=None):
    '''
    .. versionadded:: 2015.8.4

    Return gluster volume info.

    name
        Optional name to retrieve only information of one volume

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.info

    '''
    cmd = 'volume info'
    if name is not None:
        cmd += ' ' + name

    root = _gluster_xml(cmd)
    if not _gluster_ok(root):
        return None

    ret = {}
    for volume in _iter(root, 'volume'):
        name = volume.find('name').text
        ret[name] = _etree_to_dict(volume)

        bricks = {}
        for i, brick in enumerate(_iter(volume, 'brick'), start=1):
            brickkey = 'brick{0}'.format(i)
            bricks[brickkey] = {'path': brick.text}
            for child in brick:
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
    if name not in volinfo:
        log.error("Cannot start non-existing volume %s", name)
        return False

    if not force and volinfo[name]['status'] == '1':
        log.info("Volume %s already started", name)
        return True

    return _gluster(cmd)


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
    volinfo = info()
    if name not in volinfo:
        log.error('Cannot stop non-existing volume %s', name)
        return False
    if int(volinfo[name]['status']) != 1:
        log.warning('Attempt to stop already stopped volume %s', name)
        return True

    cmd = 'volume stop {0}'.format(name)
    if force:
        cmd += ' force'

    return _gluster(cmd)


def delete_volume(target, stop=True):
    '''
    Deletes a gluster volume

    target
        Volume to delete

    stop
        Stop volume before delete if it is started, True by default
    '''
    volinfo = info()
    if target not in volinfo:
        log.error('Cannot delete non-existing volume %s', target)
        return False

    # Stop volume if requested to and it is running
    running = (volinfo[target]['status'] == '1')

    if not stop and running:
        # Fail if volume is running if stop is not requested
        log.error('Volume %s must be stopped before deletion', target)
        return False

    if running:
        if not stop_volume(target, force=True):
            return False

    cmd = 'volume delete {0}'.format(target)
    return _gluster(cmd)


def add_volume_bricks(name, bricks):
    '''
    Add brick(s) to an existing volume

    name
        Volume name

    bricks
        List of bricks to add to the volume
    '''

    volinfo = info()
    if name not in volinfo:
        log.error('Volume %s does not exist, cannot add bricks', name)
        return False

    new_bricks = []

    cmd = 'volume add-brick {0}'.format(name)

    if isinstance(bricks, six.string_types):
        bricks = [bricks]

    volume_bricks = [x['path'] for x in volinfo[name]['bricks'].values()]

    for brick in bricks:
        if brick in volume_bricks:
            log.debug(
                'Brick %s already in volume %s...excluding from command',
                brick,
                name)
        else:
            new_bricks.append(brick)

    if len(new_bricks) > 0:
        for brick in new_bricks:
            cmd += ' {0}'.format(brick)
        return _gluster(cmd)
    return True


def enable_quota_volume(name):
    '''
    Enable quota on a glusterfs volume.

    name
        Name of the gluster volume
    '''

    cmd = 'volume quota {0} enable'.format(name)
    if not _gluster(cmd):
        return False
    return True


def disable_quota_volume(name):
    '''
    Disable quota on a glusterfs volume.

    name
        Name of the gluster volume
    '''

    cmd = 'volume quota {0} disable'.format(name)
    if not _gluster(cmd):
        return False
    return True


def set_quota_volume(name, path, size, enable_quota=False):
    '''
    Set quota to glusterfs volume.

    name
        Name of the gluster volume

    path
        Folder path for restriction in volume ("/")

    size
        Hard-limit size of the volume (MB/GB)

    enable_quota
        Enable quota before set up restriction

    CLI Example:

    .. code-block:: bash

        salt '*' glusterfs.set_quota_volume <volume> <path> <size> enable_quota=True

    '''
    cmd = 'volume quota {0}'.format(name)
    if path:
        cmd += ' limit-usage {0}'.format(path)
    if size:
        cmd += ' {0}'.format(size)

    if enable_quota:
        if not enable_quota_volume(name):
            pass
    if not _gluster(cmd):
        return False
    return True


def unset_quota_volume(name, path):
    '''
    Unset quota to glusterfs volume.
    name
        Name of the gluster volume
    path
        Folder path for restriction in volume
    CLI Example:
    .. code-block:: bash

        salt '*' glusterfs.unset_quota_volume <volume> <path>

    '''
    cmd = 'volume quota {0}'.format(name)
    if path:
        cmd += ' remove {0}'.format(path)

    if not _gluster(cmd):
        return False
    return True


def list_quota_volume(name):
    '''
    List quotas of glusterfs volume.
    name
        Name of the gluster volume

    '''
    cmd = 'volume quota {0}'.format(name)
    cmd += ' list'

    root = _gluster_xml(cmd)
    if not _gluster_ok(root):
        return None

    ret = {}
    for limit in _iter(root, 'limit'):
        path = limit.find('path').text
        ret[path] = _etree_to_dict(limit)

    return ret
