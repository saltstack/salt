# -*- coding: utf-8 -*-
'''
Manage Parallels Desktop VMs with ``prlctl`` and ``prlsrvctl``.  Only some of
the prlctl commands implemented so far.  Of those that have been implemented,
not all of the options may have been provided yet.  For a complete reference,
see the `Parallels Desktop Reference Guide
<http://download.parallels.com/desktop/v9/ga/docs/en_US/Parallels%20Command%20Line%20Reference%20Guide.pdf>`_.

What has not been implemented yet can be accessed through ``parallels.prlctl``
and ``parallels.prlsrvctl`` (note the preceding double dash ``--`` as
necessary):

.. code-block:: bash

    salt '*' parallels.prlctl installtools macvm runas=macdev
    salt -- '*' parallels.prlctl capture 'macvm --file macvm.display.png' runas=macdev
    salt -- '*' parallels.prlsrvctl set '--mem-limit auto' runas=macdev

.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import re
import logging
import shlex

# Import salt libs
import salt.utils.locales
import salt.utils.path
import salt.utils.yaml
from salt.exceptions import SaltInvocationError

# Import 3rd party libs
from salt.ext import six

__virtualname__ = 'parallels'
__func_alias__ = {
    'exec_': 'exec',
}
log = logging.getLogger(__name__)
# Match any GUID
GUID_REGEX = re.compile(r'{?([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})}?', re.I)


def __virtual__():
    '''
    Load this module if prlctl is available
    '''
    if not salt.utils.path.which('prlctl'):
        return (False, 'prlctl utility not available')
    if not salt.utils.path.which('prlsrvctl'):
        return (False, 'prlsrvctl utility not available')
    return __virtualname__


def _normalize_args(args):
    '''
    Return args as a list of strings
    '''
    if isinstance(args, six.string_types):
        return shlex.split(args)

    if isinstance(args, (tuple, list)):
        return [six.text_type(arg) for arg in args]
    else:
        return [six.text_type(args)]


def _find_guids(guid_string):
    '''
    Return the set of GUIDs found in guid_string

    :param str guid_string:
        String containing zero or more GUIDs.  Each GUID may or may not be
        enclosed in {}

    Example data (this string contains two distinct GUIDs):

    .. code-block::

        PARENT_SNAPSHOT_ID                      SNAPSHOT_ID
                                                {a5b8999f-5d95-4aff-82de-e515b0101b66}
        {a5b8999f-5d95-4aff-82de-e515b0101b66} *{a7345be5-ab66-478c-946e-a6c2caf14909}
    '''
    guids = []
    for found_guid in re.finditer(GUID_REGEX, guid_string):
        if found_guid.groups():
            guids.append(found_guid.group(0).strip('{}'))
    return sorted(list(set(guids)))


def prlsrvctl(sub_cmd, args=None, runas=None):
    '''
    Execute a prlsrvctl command

    .. versionadded:: 2016.11.0

    :param str sub_cmd:
        prlsrvctl subcommand to execute

    :param str args:
        The arguments supplied to ``prlsrvctl <sub_cmd>``

    :param str runas:
        The user that the prlsrvctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.prlsrvctl info runas=macdev
        salt '*' parallels.prlsrvctl usb list runas=macdev
        salt -- '*' parallels.prlsrvctl set '--mem-limit auto' runas=macdev
    '''
    # Construct command
    cmd = ['prlsrvctl', sub_cmd]
    if args:
        cmd.extend(_normalize_args(args))

    # Execute command and return output
    return __salt__['cmd.run'](cmd, runas=runas)


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
        salt -- '*' parallels.prlctl capture 'macvm --file macvm.display.png' runas=macdev
    '''
    # Construct command
    cmd = ['prlctl', sub_cmd]
    if args:
        cmd.extend(_normalize_args(args))

    # Execute command and return output
    return __salt__['cmd.run'](cmd, runas=runas)


def list_vms(name=None, info=False, all=False, args=None, runas=None, template=False):
    '''
    List information about the VMs

    :param str name:
        Name/ID of VM to list

        .. versionchanged:: 2016.11.0

            No longer implies ``info=True``

    :param str info:
        List extra information

    :param bool all:
        List all non-template VMs

    :param tuple args:
        Additional arguments given to ``prctl list``

    :param str runas:
        The user that the prlctl command will be run as

    :param bool template:
        List the available virtual machine templates.  The real virtual
        machines will not be included in the output

        .. versionadded:: 2016.11.0

    Example:

    .. code-block:: bash

        salt '*' parallels.list_vms runas=macdev
        salt '*' parallels.list_vms name=macvm info=True runas=macdev
        salt '*' parallels.list_vms info=True runas=macdev
        salt '*' parallels.list_vms ' -o uuid,status' all=True runas=macdev
    '''
    # Construct argument list
    if args is None:
        args = []
    else:
        args = _normalize_args(args)

    if name:
        args.extend([name])
    if info:
        args.append('--info')
    if all:
        args.append('--all')
    if template:
        args.append('--template')

    # Execute command and return output
    return prlctl('list', args, runas=runas)


def clone(name, new_name, linked=False, template=False, runas=None):
    '''
    Clone a VM

    .. versionadded:: 2016.11.0

    :param str name:
        Name/ID of VM to clone

    :param str new_name:
        Name of the new VM

    :param bool linked:
        Create a linked virtual machine.

    :param bool template:
        Create a virtual machine template instead of a real virtual machine.

    :param str runas:
        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.clone macvm macvm_new runas=macdev
        salt '*' parallels.clone macvm macvm_templ template=True runas=macdev
    '''
    args = [salt.utils.locales.sdecode(name), '--name', salt.utils.locales.sdecode(new_name)]
    if linked:
        args.append('--linked')
    if template:
        args.append('--template')
    return prlctl('clone', args, runas=runas)


def delete(name, runas=None):
    '''
    Delete a VM

    .. versionadded:: 2016.11.0

    :param str name:
        Name/ID of VM to clone

    :param str runas:
        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.exec macvm 'find /etc/paths.d' runas=macdev
    '''
    return prlctl('delete', salt.utils.locales.sdecode(name), runas=runas)


def exists(name, runas=None):
    '''
    Query whether a VM exists

    .. versionadded:: 2016.11.0

    :param str name:
        Name/ID of VM

    :param str runas:
        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.exists macvm runas=macdev
    '''
    vm_info = list_vms(name, info=True, runas=runas).splitlines()
    for info_line in vm_info:
        if 'Name: {0}'.format(name) in info_line:
            return True
    return False


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
    return prlctl('start', salt.utils.locales.sdecode(name), runas=runas)


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
    args = [salt.utils.locales.sdecode(name)]
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
    return prlctl('restart', salt.utils.locales.sdecode(name), runas=runas)


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
    return prlctl('reset', salt.utils.locales.sdecode(name), runas=runas)


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
    return prlctl('status', salt.utils.locales.sdecode(name), runas=runas)


def exec_(name, command, runas=None):
    '''
    Run a command on a VM

    :param str name:
        Name/ID of VM whose exec will be returned

    :param str command:
        Command to run on the VM

    :param str runas:
        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.exec macvm 'find /etc/paths.d' runas=macdev
    '''
    # Construct argument list
    args = [salt.utils.locales.sdecode(name)]
    args.extend(_normalize_args(command))

    # Execute command and return output
    return prlctl('exec', args, runas=runas)


def snapshot_id_to_name(name, snap_id, strict=False, runas=None):
    '''
    Attempt to convert a snapshot ID to a snapshot name.  If the snapshot has
    no name or if the ID is not found or invalid, an empty string will be returned

    :param str name:
        Name/ID of VM whose snapshots are inspected

    :param str snap_id:
        ID of the snapshot

    :param bool strict:
        Raise an exception if a name cannot be found for the given ``snap_id``

    :param str runas:
        The user that the prlctl command will be run as

    Example data

    .. code-block:: yaml

        ID: {a5b8999f-5d95-4aff-82de-e515b0101b66}
        Name: original
        Date: 2016-03-04 10:50:34
        Current: yes
        State: poweroff
        Description: original state

    CLI Example:

    .. code-block:: bash

        salt '*' parallels.snapshot_id_to_name macvm a5b8999f-5d95-4aff-82de-e515b0101b66 runas=macdev
    '''
    # Validate VM name and snapshot ID
    name = salt.utils.locales.sdecode(name)
    if not re.match(GUID_REGEX, snap_id):
        raise SaltInvocationError(
            'Snapshot ID "{0}" is not a GUID'.format(salt.utils.locales.sdecode(snap_id))
        )

    # Get the snapshot information of the snapshot having the requested ID
    info = prlctl('snapshot-list', [name, '--id', snap_id], runas=runas)

    # Parallels desktop returned no information for snap_id
    if not len(info):
        raise SaltInvocationError(
            'No snapshots for VM "{0}" have ID "{1}"'.format(name, snap_id)
        )

    # Try to interpret the information
    try:
        data = salt.utils.yaml.safe_load(info)
    except salt.utils.yaml.YAMLError as err:
        log.warning(
            'Could not interpret snapshot data returned from prlctl: %s', err
        )
        data = {}

    # Find the snapshot name
    if isinstance(data, dict):
        snap_name = data.get('Name', '')
        # If snapshot name is of type NoneType, then the snapshot is unnamed
        if snap_name is None:
            snap_name = ''
    else:
        log.warning(
            'Could not interpret snapshot data returned from prlctl: '
            'data is not formed as a dictionary: %s', data
        )
        snap_name = ''

    # Raise or return the result
    if not snap_name and strict:
        raise SaltInvocationError(
            'Could not find a snapshot name for snapshot ID "{0}" of VM '
            '"{1}"'.format(snap_id, name)
        )
    return salt.utils.locales.sdecode(snap_name)


def snapshot_name_to_id(name, snap_name, strict=False, runas=None):
    '''
    Attempt to convert a snapshot name to a snapshot ID.  If the name is not
    found an empty string is returned.  If multiple snapshots share the same
    name, a list will be returned

    :param str name:
        Name/ID of VM whose snapshots are inspected

    :param str snap_name:
        Name of the snapshot

    :param bool strict:
        Raise an exception if multiple snapshot IDs are found

    :param str runas:
        The user that the prlctl command will be run as

    CLI Example:

    .. code-block:: bash

        salt '*' parallels.snapshot_id_to_name macvm original runas=macdev
    '''
    # Validate VM and snapshot names
    name = salt.utils.locales.sdecode(name)
    snap_name = salt.utils.locales.sdecode(snap_name)

    # Get a multiline string containing all the snapshot GUIDs
    info = prlctl('snapshot-list', name, runas=runas)

    # Get a set of all snapshot GUIDs in the string
    snap_ids = _find_guids(info)

    # Try to match the snapshot name to an ID
    named_ids = []
    for snap_id in snap_ids:
        if snapshot_id_to_name(name, snap_id, runas=runas) == snap_name:
            named_ids.append(snap_id)

    # Return one or more IDs having snap_name or raise an error upon
    # non-singular names
    if len(named_ids) == 0:
        raise SaltInvocationError(
            'No snapshots for VM "{0}" have name "{1}"'.format(name, snap_name)
        )
    elif len(named_ids) == 1:
        return named_ids[0]
    else:
        multi_msg = ('Multiple snapshots for VM "{0}" have name '
                     '"{1}"'.format(name, snap_name))
        if strict:
            raise SaltInvocationError(multi_msg)
        else:
            log.warning(multi_msg)
        return named_ids


def _validate_snap_name(name, snap_name, strict=True, runas=None):
    '''
    Validate snapshot name and convert to snapshot ID

    :param str name:
        Name/ID of VM whose snapshot name is being validated

    :param str snap_name:
        Name/ID of snapshot

    :param bool strict:
        Raise an exception if multiple snapshot IDs are found

    :param str runas:
        The user that the prlctl command will be run as
    '''
    snap_name = salt.utils.locales.sdecode(snap_name)

    # Try to convert snapshot name to an ID without {}
    if re.match(GUID_REGEX, snap_name):
        return snap_name.strip('{}')
    else:
        return snapshot_name_to_id(name, snap_name, strict=strict, runas=runas)


def list_snapshots(name, snap_name=None, tree=False, names=False, runas=None):
    '''
    List the snapshots

    :param str name:
        Name/ID of VM whose snapshots will be listed

    :param str snap_id:
        Name/ID of snapshot to display information about.  If ``tree=True`` is
        also specified, display the snapshot subtree having this snapshot as
        the root snapshot

    :param bool tree:
        List snapshots in tree format rather than tabular format

    :param bool names:
        List snapshots as ID, name pairs

    :param str runas:
        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.list_snapshots macvm runas=macdev
        salt '*' parallels.list_snapshots macvm tree=True runas=macdev
        salt '*' parallels.list_snapshots macvm snap_name=original runas=macdev
        salt '*' parallels.list_snapshots macvm names=True runas=macdev
    '''
    # Validate VM and snapshot names
    name = salt.utils.locales.sdecode(name)
    if snap_name:
        snap_name = _validate_snap_name(name, snap_name, runas=runas)

    # Construct argument list
    args = [name]
    if tree:
        args.append('--tree')
    if snap_name:
        args.extend(['--id', snap_name])

    # Execute command
    res = prlctl('snapshot-list', args, runas=runas)

    # Construct ID, name pairs
    if names:
        # Find all GUIDs in the result
        snap_ids = _find_guids(res)

        # Try to find the snapshot names
        ret = '{0:<38}  {1}\n'.format('Snapshot ID', 'Snapshot Name')
        for snap_id in snap_ids:
            snap_name = snapshot_id_to_name(name, snap_id, runas=runas)
            ret += ('{{{0}}}  {1}\n'.format(snap_id, salt.utils.locales.sdecode(snap_name)))
        return ret

    # Return information directly from parallels desktop
    else:
        return res


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
    # Validate VM and snapshot names
    name = salt.utils.locales.sdecode(name)
    if snap_name:
        snap_name = salt.utils.locales.sdecode(snap_name)

    # Construct argument list
    args = [name]
    if snap_name:
        args.extend(['--name', snap_name])
    if desc:
        args.extend(['--description', desc])

    # Execute command and return output
    return prlctl('snapshot', args, runas=runas)


def delete_snapshot(name, snap_name, runas=None, all=False):
    '''
    Delete a snapshot

    .. note::

        Deleting a snapshot from which other snapshots are dervied will not
        delete the derived snapshots

    :param str name:
        Name/ID of VM whose snapshot will be deleted

    :param str snap_name:
        Name/ID of snapshot to delete

    :param str runas:
        The user that the prlctl command will be run as

    :param bool all:
        Delete all snapshots having the name given

        .. versionadded:: 2016.11.0

    Example:

    .. code-block:: bash

        salt '*' parallels.delete_snapshot macvm 'unneeded snapshot' runas=macdev
        salt '*' parallels.delete_snapshot macvm 'Snapshot for linked clone' all=True runas=macdev
    '''
    # strict means raise an error if multiple snapshot IDs found for the name given
    strict = not all

    # Validate VM and snapshot names
    name = salt.utils.locales.sdecode(name)
    snap_ids = _validate_snap_name(name, snap_name, strict=strict, runas=runas)
    if isinstance(snap_ids, six.string_types):
        snap_ids = [snap_ids]

    # Delete snapshot(s)
    ret = {}
    for snap_id in snap_ids:
        snap_id = snap_id.strip('{}')
        # Construct argument list
        args = [name, '--id', snap_id]

        # Execute command
        ret[snap_id] = prlctl('snapshot-delete', args, runas=runas)

    # Return results
    ret_keys = list(ret.keys())
    if len(ret_keys) == 1:
        return ret[ret_keys[0]]
    else:
        return ret


def revert_snapshot(name, snap_name, runas=None):
    '''
    Revert a VM to a snapshot

    :param str name:
        Name/ID of VM to revert to a snapshot

    :param str snap_name:
        Name/ID of snapshot to revert to

    :param str runas:
        The user that the prlctl command will be run as

    Example:

    .. code-block:: bash

        salt '*' parallels.revert_snapshot macvm base-with-updates runas=macdev
    '''
    # Validate VM and snapshot names
    name = salt.utils.locales.sdecode(name)
    snap_name = _validate_snap_name(name, snap_name, runas=runas)

    # Construct argument list
    args = [name, '--id', snap_name]

    # Execute command and return output
    return prlctl('snapshot-switch', args, runas=runas)
