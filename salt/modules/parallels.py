# -*- coding: utf-8 -*-
'''
Manage Parallels Desktop VMs with prlctl

http://download.parallels.com/desktop/v9/ga/docs/en_US/Parallels%20Command%20Line%20Reference%20Guide.pdf

.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import python libs
import logging
import shlex

# Import salt libs
import salt.utils
from salt.exceptions import SaltInvocationError

# Import 3rd party libs
import salt.ext.six as six

__virtualname__ = 'parallels'
log = logging.getLogger(__name__)


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


def prlctl(sub_cmd, args=None):
    '''
    Execute a prlctl command

    :param str sub_cmd:

        prlctl subcommand to execute

    :param str args:

        The arguments supplied to ``prlctl <sub_cmd>``

    Example:

    .. code-block:: bash

        salt '*' parallels.prlctl user list
        salt '*' parallels.prlctl exec 'macvm uname'
    '''
    # Construct command
    cmd = ['prlctl', sub_cmd]
    if args:
        cmd.extend(_normalize_args(args))

    # Execute command and return output
    return __salt__['cmd.run'](cmd)


def list_vms(name=None, info=False, args=None):
    '''
    List information about the VMs

    :param str name:

        Name/ID of VM to list; implies ``info=True``

    :param str info:

        List extra information

    :param tuple args:

        Additional arguments given to ``prctl list``.  This argument is
        mutually exclusive with the ``name`` and ``info`` arguments

    Example:

    .. code-block:: bash

        salt '*' parallels.list_vms
        salt '*' parallels.list_vms name=macvm
        salt '*' parallels.list_vms info=True
        salt '*' parallels.list_vms '--all -o uuid,status --info'
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

    # Execute command and return output
    return prlctl('list', args)


def start(name):
    '''
    Start a VM

    :param str name:

        Name/ID of VM to start

    Example:

    .. code-block:: bash

        salt '*' parallels.start macvm
    '''
    return prlctl('start', name)


def stop(name, kill=False):
    '''
    Stop a VM

    :param str name:

        Name/ID of VM to stop

    :param bool kill:

        Perform a hard shutdown

    Example:

    .. code-block:: bash

        salt '*' parallels.stop macvm
        salt '*' parallels.stop macvm kill=True
    '''
    # Construct argument list
    args = [name]
    if kill:
        args.append('--kill')

    # Execute command and return output
    return prlctl('stop', args)


def restart(name):
    '''
    Restart a VM by gracefully shutting it down and then restarting
    it

    :param str name:

        Name/ID of VM to restart

    Example:

    .. code-block:: bash

        salt '*' parallels.restart macvm
    '''
    return prlctl('restart', name)


def reset(name):
    '''
    Reset a VM by performing a hard shutdown and then a restart

    :param str name:

        Name/ID of VM to reset

    Example:

    .. code-block:: bash

        salt '*' parallels.reset macvm
    '''
    return prlctl('reset', name)


def status(name):
    '''
    Status of a VM

    :param str name:

        Name/ID of VM whose status will be returned

    Example:

    .. code-block:: bash

        salt '*' parallels.status macvm
    '''
    return prlctl('status', name)


def list_snapshots(name, id=None, tree=False):
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

    Example:

    .. code-block:: bash

        salt '*' parallels.list_snapshots macvm
        salt '*' parallels.list_snapshots macvm tree=True
        salt '*' parallels.list_snapshots macvm id=eb56cd24-977f-43e6-b72f-5dcb75e815ad
    '''
    # Construct argument list
    args = [name]
    if tree:
        args.append('--tree')
    if id:
        args.extend(['--id', id])

    # Execute command and return output
    return prlctl('snapshot-list', args)


def snapshot(name, snapshot=None, desc=None):
    '''
    Create a snapshot

    :param str name:

        Name/ID of VM to take a snapshot of

    :param str snapshot:

        Name of snapshot

    :param str desc:

        Description of snapshot

    Example:

    .. code-block:: bash

        salt '*' parallels.create_snapshot macvm snapshot=macvm-original
        salt '*' parallels.create_snapshot macvm snapshot=macvm-updates desc='clean install with updates'
    '''
    # Construct argument list
    args = [name]
    if snapshot:
        args.extend(['--name', snapshot])
    if desc:
        args.extend(['--description', desc])

    # Execute command and return output
    return prlctl('snapshot', args)


def delete_snapshot(name, id):
    '''
    Delete a snapshot

    .. note::

        Deleting a snapshot from which other snapshots are dervied will not
        delete the derived snapshots

    :param str name:

        Name/ID of VM whose snapshot will be deleted

    :param str id:

        ID of snapshot to delete

    Example:

    .. code-block:: bash

        salt '*' parallels.delete_snapshot macvm eb56cd24-977f-43e6-b72f-5dcb75e815ad
    '''
    # Construct argument list
    args = [name, '--id', id]

    # Execute command and return output
    return prlctl('snapshot-delete', args)


def revert_snapshot(name, id):
    '''
    Revert a VM to a snapshot

    :param str name:

        Name/ID of VM to revert to a snapshot

    :param str id:

        ID of snapshot to revert to

    Example:

    .. code-block:: bash

        salt '*' parallels.revert_snapshot macvm eb56cd24-977f-43e6-b72f-5dcb75e815ad
    '''
    # Construct argument list
    args = [name, '--id', id]

    # Execute command and return output
    return prlctl('snapshot-switch', args)
