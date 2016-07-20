# -*- coding: utf-8 -*-
'''
Salt interface to ZFS commands

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Some std libraries that are made
# use of.
import re
import sys

# Import Salt libs
import salt.utils
import salt.modules.cmdmod
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)

# Function alias to set mapping.
__func_alias__ = {
    'list_': 'list',
}


@decorators.memoize
def _check_zfs():
    '''
    Looks to see if zfs is present on the system.
    '''
    # Get the path to the zfs binary.
    return salt.utils.which('zfs')


def _available_commands():
    '''
    List available commands based on 'zfs -?'. Returns a dict.
    '''
    zfs_path = _check_zfs()
    if not zfs_path:
        return False

    ret = {}
    res = __salt__['cmd.run_stderr'](
        '{0} -?'.format(zfs_path),
        output_loglevel='trace',
        ignore_retcode=True
    )

    # This bit is dependent on specific output from `zfs -?` - any major changes
    # in how this works upstream will require a change.
    for line in res.splitlines():
        if re.match('	[a-zA-Z]', line):
            cmds = line.split(' ')[0].split('|')
            doc = ' '.join(line.split(' ')[1:])
            for cmd in [cmd.strip() for cmd in cmds]:
                if cmd not in ret:
                    ret[cmd] = doc
    return ret


def _exit_status(retcode):
    '''
    Translate exit status of zfs
    '''
    ret = {0: 'Successful completion.',
           1: 'An error occurred.',
           2: 'Usage error.'
           }[retcode]
    return ret


def __virtual__():
    '''
    Makes sure that ZFS kernel module is loaded.
    '''
    on_freebsd = __grains__['kernel'] == 'FreeBSD'
    on_linux = __grains__['kernel'] == 'Linux'

    cmd = ''
    if on_freebsd:
        cmd = 'kldstat -q -m zfs'
    elif on_linux:
        modinfo = salt.utils.which('modinfo')
        if modinfo:
            cmd = '{0} zfs'.format(modinfo)
        else:
            cmd = 'ls /sys/module/zfs'

    if cmd and salt.modules.cmdmod.retcode(
        cmd, output_loglevel='quiet', ignore_retcode=True
    ) == 0:
        # Build dynamic functions and allow loading module
        _build_zfs_cmd_list()
        return 'zfs'
    return False


def _add_doc(func, doc, prefix='\n\n    '):
    '''
    Add documentation to a function
    '''
    if not func.__doc__:
        func.__doc__ = ''
    func.__doc__ += '{0}{1}'.format(prefix, doc)


def _make_function(cmd_name, doc):
    '''
    Returns a function based on the command name.
    '''
    def _cmd(*args):
        # Define a return value.
        ret = {}

        # Run the command.
        res = __salt__['cmd.run_all'](
                '{0} {1} {2}'.format(
                    _check_zfs(),
                    cmd_name,
                    ' '.join(args)
                    )
                )

        # Make a note of the error in the return object if retcode
        # not 0.
        if res['retcode'] != 0:
            ret['Error'] = _exit_status(res['retcode'])

        # Set the output to be splitlines for now.
        ret = res['stdout'].splitlines()

        return ret

    _add_doc(_cmd, 'This function is dynamically generated.', '\n    ')
    _add_doc(_cmd, doc)
    _add_doc(_cmd, '\n    CLI Example:\n\n')
    _add_doc(_cmd, '\n        salt \'*\' zfs.{0} <args>'.format(cmd_name))

    # At this point return the function we've just defined.
    return _cmd


def _build_zfs_cmd_list():
    '''
    Run through zfs command options, and build equivalent functions dynamically
    '''
    # Run through all the available commands
    if _check_zfs():
        available_cmds = _available_commands()
        for available_cmd in available_cmds:

            # Set the output from _make_function to be 'available_cmd_'.
            # i.e. 'list' becomes 'list_' in local module.
            setattr(
                    sys.modules[__name__],
                    '{0}_'.format(available_cmd),
                    _make_function(available_cmd, available_cmds[available_cmd])
                    )

            # Update the function alias so that salt finds the functions properly.
            __func_alias__['{0}_'.format(available_cmd)] = available_cmd


def exists(name):
    '''
    .. versionadded:: 2015.5.0

    Check if a ZFS filesystem or volume or snapshot exists.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.exists myzpool/mydataset
    '''
    zfs = _check_zfs()
    cmd = '{0} list {1}'.format(zfs, name)
    res = __salt__['cmd.run'](cmd, ignore_retcode=True)
    if "dataset does not exist" in res or "invalid dataset name" in res:
        return False
    return True


def create(name, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Create a ZFS File System.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.create myzpool/mydataset [create_parent=True|False]

    .. note::

        ZFS properties can be specified at the time of creation of the filesystem by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

        Example:

        .. code-block:: bash

            salt '*' zfs.create myzpool/mydataset properties="{'mountpoint': '/export/zfs', 'sharenfs': 'on'}"
    '''
    ret = {}

    zfs = _check_zfs()
    properties = kwargs.get('properties', None)
    create_parent = kwargs.get('create_parent', False)
    cmd = '{0} create'.format(zfs)

    if create_parent:
        cmd = '{0} -p'.format(cmd)

    # if zpool properties specified, then
    # create "-o property=value" pairs
    if properties:
        optlist = []
        for prop in properties:
            optlist.append('-o {0}={1}'.format(prop, properties[prop]))
        opts = ' '.join(optlist)
        cmd = '{0} {1}'.format(cmd, opts)
    cmd = '{0} {1}'.format(cmd, name)

    # Create filesystem
    res = __salt__['cmd.run'](cmd)

    # Check and see if the dataset is available
    if not res:
        ret[name] = 'created'
        return ret
    else:
        ret['Error'] = res
    return ret


def destroy(name, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Destroy a ZFS File System.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.destroy myzpool/mydataset [force=True|False]
    '''
    ret = {}
    zfs = _check_zfs()
    force = kwargs.get('force', False)
    cmd = '{0} destroy {1}'.format(zfs, name)

    if force:
        cmd = '{0} destroy -f {1}'.format(zfs, name)

    res = __salt__['cmd.run'](cmd)
    if not res:
        ret[name] = 'Destroyed'
        return ret
    elif "dataset does not exist" in res:
        ret['Error'] = 'Cannot destroy {0}: dataset does not exist'.format(name)
    elif "operation does not apply to pools" in res:
        ret['Error'] = 'Cannot destroy {0}: use zpool.destroy to destroy the pool'.format(name)
    else:
        ret['Error'] = res
    return ret


def rename(name, new_name):
    '''
    .. versionadded:: 2015.5.0

    Rename or Relocate a ZFS File System.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.rename myzpool/mydataset myzpool/renameddataset
    '''
    ret = {}
    zfs = _check_zfs()
    cmd = '{0} rename {1} {2}'.format(zfs, name, new_name)

    res = __salt__['cmd.run'](cmd)
    if not res:
        ret[name] = 'Renamed/Relocated to {0}'.format(new_name)
        return ret
    else:
        ret['Error'] = res
    return ret


def list_(name='', **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Return a list of all datasets or a specified dataset on the system and the
    values of their used, available, referenced, and mountpoint properties.

    .. note::

        Information about the dataset and all of it\'s descendent datasets can be displayed
        by passing ``recursive=True`` on the CLI.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.list [recursive=True|False]
        salt '*' zfs.list /myzpool/mydataset [recursive=True|False]

    .. note::

        Dataset property value output can be customized by passing an additional argument called
        "properties" in the form of a python list::

            properties="[property1, property2, property3]"

        Example:

        .. code-block:: bash

            salt '*' zfs.list /myzpool/mydataset properties="[name, sharenfs, mountpoint]"

    '''
    zfs = _check_zfs()
    recursive_opt = kwargs.get('recursive', False)
    properties_opt = kwargs.get('properties', False)
    cmd = '{0} list'.format(zfs)

    if recursive_opt:
        cmd = '{0} -r'.format(cmd)

    if properties_opt:
        cmd = '{0} -o {1}'.format(cmd, ','.join(properties_opt))

    cmd = '{0} {1}'.format(cmd, name)

    res = __salt__['cmd.run_all'](cmd)

    if res['retcode'] == 0:
        dataset_list = [l for l in res['stdout'].splitlines()]
        return {'datasets': dataset_list}
    else:
        return {'Error': res['stderr']}
