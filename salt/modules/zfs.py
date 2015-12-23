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
from salt.utils.odict import OrderedDict

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
    Does not work on illumos or solaris
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
        if re.match('  [a-zA-Z]', line):
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
    on_solaris = __grains__['kernel'] == 'SunOS' and __grains__['kernelrelease'] == '5.11'

    cmd = ''
    if on_freebsd:
        cmd = 'kldstat -q -m zfs'
    elif on_linux:
        modinfo = salt.utils.which('modinfo')
        if modinfo:
            cmd = '{0} zfs'.format(modinfo)
        else:
            cmd = 'ls /sys/module/zfs'
    elif on_solaris:
        # not using salt.utils.which('zfs') to keep compatible with others
        cmd = 'which zfs'

    if cmd and salt.modules.cmdmod.retcode(
        cmd, output_loglevel='quiet', ignore_retcode=True
    ) == 0:
        # Build dynamic functions and allow loading module
        _build_zfs_cmd_list()
        return 'zfs'
    return (False, "The zfs module cannot be loaded: zfs not found")


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
            ret['error'] = _exit_status(res['retcode'])

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

    name : string
        name of dataset

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.exists myzpool/mydataset
    '''
    zfs = _check_zfs()
    cmd = '{0} list {1}'.format(zfs, name)
    res = __salt__['cmd.run_all'](cmd, ignore_retcode=True)

    return res['retcode'] == 0


def create(name, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Create a ZFS File System.

    name : string
        name of dataset or volume
    volume_size : string
        if specified, a zvol will be created instead of a dataset
    sparse : boolean
        create sparse volume
    create_parent : boolean
        creates all the non-existing parent datasets. any property specified on the
        command line using the -o option is ignored.
    properties : dict
        additional zfs properties (-o)

    .. note::

        ZFS properties can be specified at the time of creation of the filesystem by
        passing an additional argument called "properties" and specifying the properties
        with their respective values in the form of a python dictionary::

            properties="{'property1': 'value1', 'property2': 'value2'}"

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.create myzpool/mydataset [create_parent=True|False]
        salt '*' zfs.create myzpool/mydataset properties="{'mountpoint': '/export/zfs', 'sharenfs': 'on'}"
        salt '*' zfs.create myzpool/volume volume_size=1G [sparse=True|False]`
        salt '*' zfs.create myzpool/volume volume_size=1G properties="{'volblocksize': '512'}" [sparse=True|False]

    '''
    ret = {}

    zfs = _check_zfs()
    properties = kwargs.get('properties', None)
    create_parent = kwargs.get('create_parent', False)
    volume_size = kwargs.get('volume_size', None)
    sparse = kwargs.get('sparse', False)
    cmd = '{0} create'.format(zfs)

    if create_parent:
        cmd = '{0} -p'.format(cmd)

    if volume_size and sparse:
        cmd = '{0} -s'.format(cmd)

    # if zpool properties specified, then
    # create "-o property=value" pairs
    if properties:
        optlist = []
        for prop in properties:
            optlist.append('-o {0}={1}'.format(prop, properties[prop]))
        opts = ' '.join(optlist)
        cmd = '{0} {1}'.format(cmd, opts)

    if volume_size:
        cmd = '{0} -V {1}'.format(cmd, volume_size)

    # append name
    cmd = '{0} {1}'.format(cmd, name)

    # Create filesystem
    res = __salt__['cmd.run_all'](cmd)

    # Check and see if the dataset is available
    if res['retcode'] != 0:
        ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'created'

    return ret


def destroy(name, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Destroy a ZFS File System.

    name : string
        name of dataset, volume, or snapshot
    force : boolean
        force an unmount of any file systems using the unmount -f command.
    recursive : boolean
        recursively destroy all children. (-r)
    recursive_all : boolean
        recursively destroy all dependents, including cloned file systems
        outside the target hierarchy. (-R)

    .. warning::
        watch out when using recursive and recursive_all

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.destroy myzpool/mydataset [force=True|False]
    '''
    ret = {}
    zfs = _check_zfs()
    force = kwargs.get('force', False)
    recursive = kwargs.get('recursive', False)
    recursive_all = kwargs.get('recursive_all', False)
    cmd = '{0} destroy'.format(zfs)

    if recursive_all:
        cmd = '{0} -R'.format(cmd)

    if force:
        cmd = '{0} -f'.format(cmd)

    if recursive:
        cmd = '{0} -r'.format(cmd)

    cmd = '{0} {1}'.format(cmd, name)
    res = __salt__['cmd.run_all'](cmd)

    if res['retcode'] != 0:
        if "operation does not apply to pools" in res['stderr']:
            ret[name] = '{0}, use zpool.destroy to destroy the pool'.format(res['stderr'].splitlines()[0])
        if "filesystem has children" in res['stderr']:
            ret[name] = '{0}, you can add the "recursive=True" parameter'.format(res['stderr'].splitlines()[0])
        else:
            ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'destroyed'

    return ret


def rename(name, new_name, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Rename or Relocate a ZFS File System.

    name : string
        name of dataset, volume, or snapshot
    new_name : string
        new name of dataset, volume, or snapshot
    force : boolean
        force unmount any filesystems that need to be unmounted in the process.
    create_parent : boolean
        creates all the nonexistent parent datasets. Datasets created in
        this manner are automatically mounted according to the mountpoint
        property inherited from their parent.
    recursive : boolean
        recursively rename the snapshots of all descendent datasets.
        snapshots are the only dataset that can be renamed recursively.

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.rename myzpool/mydataset myzpool/renameddataset
    '''
    ret = {}
    zfs = _check_zfs()
    create_parent = kwargs.get('create_parent', False)
    force = kwargs.get('force', False)
    recursive = kwargs.get('recursive', False)

    # fix up conflicting parameters
    if recursive:
        if '@' in name:  # -p and -f don't work with -r
            create_parent = False
            force = False
        else:  # -r only works with snapshots
            recursive = False
    if create_parent and '@' in name:  # doesn't work with snapshots
        create_parent = False

    res = __salt__['cmd.run_all']('{zfs} rename {force}{create_parent}{recursive}{name} {new_name}'.format(
        zfs=zfs,
        force='-f ' if force else '',
        create_parent='-p ' if create_parent else '',
        recursive='-r ' if recursive else '',
        name=name,
        new_name=new_name
    ))

    if res['retcode'] != 0:
        ret[name] = res['stderr'] if 'stderr' in res else res['stdout']
    else:
        ret[name] = 'renamed to {0}'.format(new_name)

    return ret


def list_(name=None, **kwargs):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: Boron

    Return a list of all datasets or a specified dataset on the system and the
    values of their used, available, referenced, and mountpoint properties.

    name : string
        name of dataset, volume, or snapshot
    recursive : boolean
        recursively list children
    depth : int
        limit recursion to depth
    properties : string
        comma-seperated list of properties to list, the name property will always be added
    type : string
        comma-separated list of types to display, where type is one of
        filesystem, snapshot, volume, bookmark, or all.
    sort : string
        property to sort on (default = name)
    order : string [ascending|descending]
        sort order (default = ascending)

    CLI Example:

    .. code-block:: bash

        salt '*' zfs.list
        salt '*' zfs.list myzpool/mydataset [recursive=True|False]
        salt '*' zfs.list myzpool/mydataset properties="sharenfs,mountpoint"


    '''
    ret = OrderedDict()
    zfs = _check_zfs()
    recursive = kwargs.get('recursive', False)
    depth = kwargs.get('depth', 0)
    properties = kwargs.get('properties', 'used,avail,refer,mountpoint')
    sort = kwargs.get('sort', None)
    ltype = kwargs.get('type', None)
    order = kwargs.get('order', 'ascending')
    cmd = '{0} list -H'.format(zfs)

    # filter on type
    if ltype:
        cmd = '{0} -t {1}'.format(cmd, ltype)

    # recursively list
    if recursive:
        cmd = '{0} -r'.format(cmd)
        if depth:
            cmd = '{0} -d {1}'.format(cmd, depth)

    # add properties
    properties = properties.split(',')
    if 'name' in properties:  # ensure name is first property
        properties.remove('name')
    properties.insert(0, 'name')
    cmd = '{0} -o {1}'.format(cmd, ','.join(properties))

    # sorting
    if sort and sort in properties:
        if order.startswith('a'):
            cmd = '{0} -s {1}'.format(cmd, sort)
        else:
            cmd = '{0} -S {1}'.format(cmd, sort)

    # add name if set
    if name:
        cmd = '{0} {1}'.format(cmd, name)

    # parse output
    res = __salt__['cmd.run_all'](cmd)
    if res['retcode'] == 0:
        for ds in [l for l in res['stdout'].splitlines()]:
            ds = ds.split("\t")
            ds_data = {}

            for prop in properties:
                ds_data[prop] = ds[properties.index(prop)]

            ret[ds_data['name']] = ds_data
            del ret[ds_data['name']]['name']
    else:
        ret['error'] = res['stderr'] if 'stderr' in res else res['stdout']

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
