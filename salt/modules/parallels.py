# -*- coding: utf-8 -*-
'''
Manage Parallels Desktop VMs with prlctl

http://download.parallels.com/desktop/v9/ga/docs/en_US/Parallels%20Command%20Line%20Reference%20Guide.pdf

.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import python libs
import re
import logging
import shlex
import yaml

# Import salt libs
import salt.utils
from salt.exceptions import SaltInvocationError

# Import 3rd party libs
import salt.ext.six as six

__virtualname__ = 'parallels'
log = logging.getLogger(__name__)
# Match any GUID
GUID_REGEX = re.compile(r'([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})', re.I)


def __virtual__():
    '''
    Load this module if prlctl is available
    '''
    if not salt.utils.which('prlctl'):
        return (False, 'Cannot load prlctl module: prlctl utility not available')
    return __virtualname__


def _normalize_args(args):
    '''
    Return args as a list of strings
    '''
    if isinstance(args, six.string_types):
        return shlex.split(args)

    if isinstance(args, (tuple, list)):
        return [str(arg) for arg in args]
    else:
        return [str(args)]


def prlctl(sub_cmd, args=None, runas=None):
    '''
    Execute a prlctl command

    :param str sub_cmd:

        prlctl subcommand to execute

    :param str args:

        The arguments supplied to ``prlctl <sub_cmd>``

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.prlctl user list runas=macdev
        salt '*' parallels.prlctl exec 'macvm uname' runas=macdev
    '''
    # Construct command
    cmd = ['prlctl', sub_cmd]
    if args:
        cmd.extend(_normalize_args(args))

    # Execute command and return output
    return __salt__['cmd.run'](cmd, runas=runas)


def list_vms(name=None, info=False, all=False, args=None, runas=None):
    '''
    List information about the VMs

    :param str name:

        Name/ID of VM to list; implies ``info=True``

    :param str info:

        List extra information

    :param bool all:

        Also list non-running VMs

    :param tuple args:

        Additional arguments given to ``prctl list``.  This argument is
        mutually exclusive with the other arguments

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.list_vms runas=macdev
        salt '*' parallels.list_vms name=macvm runas=macdev
        salt '*' parallels.list_vms info=True runas=macdev
        salt '*' parallels.list_vms ' -o uuid,status' all=True runas=macdev
    '''
    # Construct argument list
    if args is None:
        args = []
    else:
        args = _normalize_args(args)

    if name:
        args.extend(['--info', name])
    elif info:
        args.append('--info')

    if all:
        args.append('--all')

    # Execute command and return output
    return prlctl('list', args, runas=runas)


def start(name, runas=None):
    '''
    Start a VM

    :param str name:

        Name/ID of VM to start

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.start macvm runas=macdev
    '''
    return prlctl('start', name, runas=runas)


def stop(name, kill=False, runas=None):
    '''
    Stop a VM

    :param str name:

        Name/ID of VM to stop

    :param bool kill:

        Perform a hard shutdown

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.stop macvm runas=macdev
        salt '*' parallels.stop macvm kill=True runas=macdev
    '''
    # Construct argument list
    args = [name]
    if kill:
        args.append('--kill')

    # Execute command and return output
    return prlctl('stop', args, runas=runas)


def restart(name, runas=None):
    '''
    Restart a VM by gracefully shutting it down and then restarting
    it

    :param str name:

        Name/ID of VM to restart

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.restart macvm runas=macdev
    '''
    return prlctl('restart', name, runas=runas)


def reset(name, runas=None):
    '''
    Reset a VM by performing a hard shutdown and then a restart

    :param str name:

        Name/ID of VM to reset

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.reset macvm runas=macdev
    '''
    return prlctl('reset', name, runas=runas)


def status(name, runas=None):
    '''
    Status of a VM

    :param str name:

        Name/ID of VM whose status will be returned

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.status macvm runas=macdev
    '''
    return prlctl('status', name, runas=runas)


def list_snapshots(name, id=None, tree=False, runas=None):
    '''
    List the snapshots

    :param str name:

        Name/ID of VM whose snapshots will be listed

    :param str id:

        ID of snapshot to display information about.  If ``tree=True`` is also
        specified, display the snapshot subtree having this snapshot as the
        root snapshot

    :param bool tree:

        List snapshots in tree format rather than tabular format

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.list_snapshots macvm runas=macdev
        salt '*' parallels.list_snapshots macvm tree=True runas=macdev
        salt '*' parallels.list_snapshots macvm id=eb56cd24-977f-43e6-b72f-5dcb75e815ad runas=macdev
    '''
    # Construct argument list
    args = [name]
    if tree:
        args.append('--tree')
    if id:
        args.extend(['--id', id])

    # Execute command and return output
    return prlctl('snapshot-list', args, runas=runas)


def snapshot_id_to_name(name, id, runas=None):
    '''
    Attempt to convert a snapshot ID to a snapshot name.  If the snapshot has
    no name or if the ID is not found or invalid, an empty string will be returned

    :param str name:

        Name/ID of VM whose snapshots are inspected

    :param str id:

        ID of the snapshot

    :param str runas:

        The user that the prlctl command will be run as

    Example data

    .. code-block::

        ID: {a5b8999f-5d95-4aff-82de-e515b0101b66}
        Name: original
        Date: 2016-03-04 10:50:34
        Current: yes
        State: poweroff
        Description: 3/4/16

    CLI Example:

    .. code-block:: bash

        salt '*' parallels.snapshot_id_to_name macvm a5b8999f-5d95-4aff-82de-e515b0101b66 runas=macdev
    '''
    # Get the snapshot information of the snapshot having the requested ID
    info = list_snapshots(name, id=id, runas=runas)

    # Try to interpret the information.  This should be fine if parallels
    # desktop does not change its format too much, otherwise more custom logic
    # will be needed here to extract the name
    try:
        data = yaml.safe_load(info)
        if isinstance(data, dict):
            snap_name = data.get('Name', '')
            # Do not return None if snapshot name is of type NoneType
            return snap_name if snap_name else ''
        else:
            return ''
    except yaml.YAMLError:
        return ''


def snapshot_name_to_id(name, snap_name, runas=None):
    '''
    Attempt to convert a snapshot name to a snapshot ID.  If the name is not
    found an empty string is returned.  If multiple snapshots share the same
    name, it is not defined which ID will be returned

    :param str name:

        Name/ID of VM whose snapshots are inspected

    :param str snap_name:

        Name of the snapshot

    :param str runas:

        The user that the prlctl command will be run as

    CLI Example:

    .. code-block:: bash

        salt '*' parallels.snapshot_id_to_name macvm original runas=macdev
    '''
    # Get a multiline string containing all the snapshot GUIDs
    res = list_snapshots(name, runas=runas)

    # Find all GUIDs in the string
    ids = set([found.group(0) for found in re.finditer(GUID_REGEX, res)])

    # Try to match the snapshot name to an ID
    for id in ids:
        if snapshot_id_to_name(name, id, runas=runas) == snap_name:
            return id
    return ''


def snapshot(name, snap_name=None, desc=None, runas=None):
    '''
    Create a snapshot

    :param str name:

        Name/ID of VM to take a snapshot of

    :param str snap_name:

        Name of snapshot

    :param str desc:

        Description of snapshot

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.create_snapshot macvm snap_name=macvm-original runas=macdev
        salt '*' parallels.create_snapshot macvm snap_name=macvm-updates desc='clean install with updates' runas=macdev
    '''
    # Construct argument list
    args = [name]
    if snap_name:
        args.extend(['--name', snap_name])
    if desc:
        args.extend(['--description', desc])

    # Execute command and return output
    return prlctl('snapshot', args, runas=runas)


def delete_snapshot(name, id, runas=None):
    '''
    Delete a snapshot

    .. note::

        Deleting a snapshot from which other snapshots are dervied will not
        delete the derived snapshots

    :param str name:

        Name/ID of VM whose snapshot will be deleted

    :param str id:

        ID of snapshot to delete

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.delete_snapshot macvm eb56cd24-977f-43e6-b72f-5dcb75e815ad runas=macdev
    '''
    # Construct argument list
    args = [name, '--id', id]

    # Execute command and return output
    return prlctl('snapshot-delete', args, runas=runas)


def revert_snapshot(name, id, runas=None):
    '''
    Revert a VM to a snapshot

    :param str name:

        Name/ID of VM to revert to a snapshot

    :param str id:

        ID of snapshot to revert to

    :param str runas:

        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.revert_snapshot macvm eb56cd24-977f-43e6-b72f-5dcb75e815ad runas=macdev
    '''
    # Construct argument list
    args = [name, '--id', id]

    # Execute command and return output
    return prlctl('snapshot-switch', args, runas=runas)
