# -*- coding: utf-8 -*-
'''
Support for VirtualBox using the VBoxManage command

.. versionadded:: 2016.3.0

If the ``vboxdrv`` kernel module is not loaded, this module can automatically
load it by configuring ``autoload_vboxdrv`` in ``/etc/salt/minion``:

.. code-block: yaml

    autoload_vboxdrv: True

The default for this setting is ``False``.

:depends: virtualbox
'''

from __future__ import absolute_import, print_function, unicode_literals
import re
import os.path
import logging

# pylint: disable=import-error,no-name-in-module
import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandExecutionError
# pylint: enable=import-error,no-name-in-module

# Import 3rd-party libs
from salt.ext import six

LOG = logging.getLogger(__name__)

UUID_RE = re.compile('[^{0}]'.format('a-zA-Z0-9._-'))
NAME_RE = re.compile('[^{0}]'.format('a-zA-Z0-9._-'))


def __virtual__():
    '''
    Only load the module if VBoxManage is installed
    '''
    if vboxcmd():
        if __opts__.get('autoload_vboxdrv', False) is True:
            if not __salt__['kmod.is_loaded']('vboxdrv'):
                __salt__['kmod.load']('vboxdrv')
        return True
    return (False, 'The vboxmanaged execution module failed to load: VBoxManage is not installed.')


def vboxcmd():
    '''
    Return the location of the VBoxManage command

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.vboxcmd
    '''
    return salt.utils.path.which('VBoxManage')


def list_ostypes():
    '''
    List the available OS Types

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.list_ostypes
    '''
    return list_items('ostypes', True, 'ID')


def list_nodes_min():
    '''
    Return a list of registered VMs, with minimal information

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.list_nodes_min
    '''
    ret = {}
    cmd = '{0} list vms'.format(vboxcmd())
    for line in salt.modules.cmdmod.run(cmd).splitlines():
        if not line.strip():
            continue
        comps = line.split()
        name = comps[0].replace('"', '')
        ret[name] = True
    return ret


def list_nodes_full():
    '''
    Return a list of registered VMs, with detailed information

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.list_nodes_full
    '''
    return list_items('vms', True, 'Name')


def list_nodes():
    '''
    Return a list of registered VMs

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.list_nodes
    '''
    ret = {}
    nodes = list_nodes_full()
    for node in nodes:
        ret[node] = {
            'id': nodes[node]['UUID'],
            'image': nodes[node]['Guest OS'],
            'name': nodes[node]['Name'],
            'state': None,
            'private_ips': [],
            'public_ips': [],
        }
        ret[node]['size'] = '{0} RAM, {1} CPU'.format(
            nodes[node]['Memory size'],
            nodes[node]['Number of CPUs'],
        )
    return ret


def start(name):
    '''
    Start a VM

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.start my_vm
    '''
    ret = {}
    cmd = '{0} startvm {1}'.format(vboxcmd(), name)
    ret = salt.modules.cmdmod.run(cmd).splitlines()
    return ret


def stop(name):
    '''
    Stop a VM

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.stop my_vm
    '''
    cmd = '{0} controlvm {1} poweroff'.format(vboxcmd(), name)
    ret = salt.modules.cmdmod.run(cmd).splitlines()
    return ret


def register(filename):
    '''
    Register a VM

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.register my_vm_filename
    '''
    if not os.path.isfile(filename):
        raise CommandExecutionError(
            'The specified filename ({0}) does not exist.'.format(filename)
        )

    cmd = '{0} registervm {1}'.format(vboxcmd(), filename)
    ret = salt.modules.cmdmod.run_all(cmd)
    if ret['retcode'] == 0:
        return True
    return ret['stderr']


def unregister(name, delete=False):
    '''
    Unregister a VM

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.unregister my_vm_filename
    '''
    nodes = list_nodes_min()
    if name not in nodes:
        raise CommandExecutionError(
            'The specified VM ({0}) is not registered.'.format(name)
        )

    cmd = '{0} unregistervm {1}'.format(vboxcmd(), name)
    if delete is True:
        cmd += ' --delete'
    ret = salt.modules.cmdmod.run_all(cmd)
    if ret['retcode'] == 0:
        return True
    return ret['stderr']


def destroy(name):
    '''
    Unregister and destroy a VM

    CLI Example:

    .. code-block:: bash

        salt '*' vboxmanage.destroy my_vm
    '''
    return unregister(name, True)


def create(name,
           groups=None,
           ostype=None,
           register=True,
           basefolder=None,
           new_uuid=None,
           **kwargs):
    '''
    Create a new VM

    CLI Example:

    .. code-block:: bash

        salt 'hypervisor' vboxmanage.create <name>
    '''
    nodes = list_nodes_min()
    if name in nodes:
        raise CommandExecutionError(
            'The specified VM ({0}) is already registered.'.format(name)
        )

    params = ''

    if name:
        if NAME_RE.search(name):
            raise CommandExecutionError('New VM name contains invalid characters')
        params += ' --name {0}'.format(name)

    if groups:
        if isinstance(groups, six.string_types):
            groups = [groups]
        if isinstance(groups, list):
            params += ' --groups {0}'.format(','.join(groups))
        else:
            raise CommandExecutionError(
                'groups must be either a string or a list of strings'
            )

    ostypes = list_ostypes()
    if ostype not in ostypes:
        raise CommandExecutionError(
            'The specified OS type ({0}) is not available.'.format(name)
        )
    else:
        params += ' --ostype ' + ostype

    if register is True:
        params += ' --register'

    if basefolder:
        if not os.path.exists(basefolder):
            raise CommandExecutionError('basefolder {0} was not found'.format(basefolder))
        params += ' --basefolder {0}'.format(basefolder)

    if new_uuid:
        if NAME_RE.search(new_uuid):
            raise CommandExecutionError('New UUID contains invalid characters')
        params += ' --uuid {0}'.format(new_uuid)

    cmd = '{0} create {1}'.format(vboxcmd(), params)
    ret = salt.modules.cmdmod.run_all(cmd)
    if ret['retcode'] == 0:
        return True
    return ret['stderr']


def clonevm(name=None,
            uuid=None,
            new_name=None,
            snapshot_uuid=None,
            snapshot_name=None,
            mode='machine',
            options=None,
            basefolder=None,
            new_uuid=None,
            register=False,
            groups=None,
            **kwargs):
    '''
    Clone a new VM from an existing VM

    CLI Example:

    .. code-block:: bash

        salt 'hypervisor' vboxmanage.clonevm <name> <new_name>
    '''
    if (name and uuid) or (not name and not uuid):
        raise CommandExecutionError(
            'Either a name or a uuid must be specified, but not both.'
        )

    params = ''
    nodes_names = list_nodes_min()
    nodes_uuids = list_items('vms', True, 'UUID').keys()
    if name:
        if name not in nodes_names:
            raise CommandExecutionError(
                'The specified VM ({0}) is not registered.'.format(name)
            )
        params += ' ' + name
    elif uuid:
        if uuid not in nodes_uuids:
            raise CommandExecutionError(
                'The specified VM ({0}) is not registered.'.format(name)
            )
        params += ' ' + uuid

    if snapshot_name and snapshot_uuid:
        raise CommandExecutionError(
            'Either a snapshot_name or a snapshot_uuid may be specified, but not both'
        )

    if snapshot_name:
        if NAME_RE.search(snapshot_name):
            raise CommandExecutionError('Snapshot name contains invalid characters')
        params += ' --snapshot {0}'.format(snapshot_name)
    elif snapshot_uuid:
        if UUID_RE.search(snapshot_uuid):
            raise CommandExecutionError('Snapshot name contains invalid characters')
        params += ' --snapshot {0}'.format(snapshot_uuid)

    valid_modes = ('machine', 'machineandchildren', 'all')
    if mode and mode not in valid_modes:
        raise CommandExecutionError(
            'Mode must be one of: {0} (default "machine")'.format(', '.join(valid_modes))
        )
    else:
        params += ' --mode ' + mode

    valid_options = ('link', 'keepallmacs', 'keepnatmacs', 'keepdisknames')
    if options and options not in valid_options:
        raise CommandExecutionError(
            'If specified, options must be one of: {0}'.format(', '.join(valid_options))
        )
    else:
        params += ' --options ' + options

    if new_name:
        if NAME_RE.search(new_name):
            raise CommandExecutionError('New name contains invalid characters')
        params += ' --name {0}'.format(new_name)

    if groups:
        if isinstance(groups, six.string_types):
            groups = [groups]
        if isinstance(groups, list):
            params += ' --groups {0}'.format(','.join(groups))
        else:
            raise CommandExecutionError(
                'groups must be either a string or a list of strings'
            )

    if basefolder:
        if not os.path.exists(basefolder):
            raise CommandExecutionError('basefolder {0} was not found'.format(basefolder))
        params += ' --basefolder {0}'.format(basefolder)

    if new_uuid:
        if NAME_RE.search(new_uuid):
            raise CommandExecutionError('New UUID contains invalid characters')
        params += ' --uuid {0}'.format(new_uuid)

    if register is True:
        params += ' --register'

    cmd = '{0} clonevm {1}'.format(vboxcmd(), name)
    ret = salt.modules.cmdmod.run_all(cmd)
    if ret['retcode'] == 0:
        return True
    return ret['stderr']


def clonemedium(medium,
                uuid_in=None,
                file_in=None,
                uuid_out=None,
                file_out=None,
                mformat=None,
                variant=None,
                existing=False,
                **kwargs):
    '''
    Clone a new VM from an existing VM

    CLI Example:

    .. code-block:: bash

        salt 'hypervisor' vboxmanage.clonemedium <name> <new_name>
    '''
    params = ''
    valid_mediums = ('disk', 'dvd', 'floppy')
    if medium in valid_mediums:
        params += medium
    else:
        raise CommandExecutionError(
            'Medium must be one of: {0}.'.format(', '.join(valid_mediums))
        )

    if (uuid_in and file_in) or (not uuid_in and not file_in):
        raise CommandExecutionError(
            'Either uuid_in or file_in must be used, but not both.'
        )

    if uuid_in:
        if medium == 'disk':
            item = 'hdds'
        elif medium == 'dvd':
            item = 'dvds'
        elif medium == 'floppy':
            item = 'floppies'

        items = list_items(item)

        if uuid_in not in items:
            raise CommandExecutionError('UUID {0} was not found'.format(uuid_in))
        params += ' ' + uuid_in
    elif file_in:
        if not os.path.exists(file_in):
            raise CommandExecutionError('File {0} was not found'.format(file_in))
        params += ' ' + file_in

    if (uuid_out and file_out) or (not uuid_out and not file_out):
        raise CommandExecutionError(
            'Either uuid_out or file_out must be used, but not both.'
        )

    if uuid_out:
        params += ' ' + uuid_out
    elif file_out:
        try:
            salt.utils.files.fopen(file_out, 'w').close()  # pylint: disable=resource-leakage
            os.unlink(file_out)
            params += ' ' + file_out
        except OSError:
            raise CommandExecutionError('{0} is not a valid filename'.format(file_out))

    if mformat:
        valid_mformat = ('VDI', 'VMDK', 'VHD', 'RAW')
        if mformat not in valid_mformat:
            raise CommandExecutionError(
                'If specified, mformat must be one of: {0}'.format(', '.join(valid_mformat))
            )
        else:
            params += ' --format ' + mformat

    valid_variant = ('Standard', 'Fixed', 'Split2G', 'Stream', 'ESX')
    if variant and variant not in valid_variant:
        if not os.path.exists(file_in):
            raise CommandExecutionError(
                'If specified, variant must be one of: {0}'.format(', '.join(valid_variant))
            )
        else:
            params += ' --variant ' + variant

    if existing:
        params += ' --existing'

    cmd = '{0} clonemedium {1}'.format(vboxcmd(), params)
    ret = salt.modules.cmdmod.run_all(cmd)
    if ret['retcode'] == 0:
        return True
    return ret['stderr']


def list_items(item, details=False, group_by='UUID'):
    '''
    Return a list of a specific type of item. The following items are available:

        vms
        runningvms
        ostypes
        hostdvds
        hostfloppies
        intnets
        bridgedifs
        hostonlyifs
        natnets
        dhcpservers
        hostinfo
        hostcpuids
        hddbackends
        hdds
        dvds
        floppies
        usbhost
        usbfilters
        systemproperties
        extpacks
        groups
        webcams
        screenshotformats

    CLI Example:

    .. code-block:: bash

        salt 'hypervisor' vboxmanage.items <item>
        salt 'hypervisor' vboxmanage.items <item> details=True
        salt 'hypervisor' vboxmanage.items <item> details=True group_by=Name

    Some items do not display well, or at all, unless ``details`` is set to
    ``True``. By default, items are grouped by the ``UUID`` field, but not all
    items contain that field. In those cases, another field must be specified.
    '''
    types = (
        'vms', 'runningvms', 'ostypes', 'hostdvds', 'hostfloppies', 'intnets',
        'bridgedifs', 'hostonlyifs', 'natnets', 'dhcpservers', 'hostinfo',
        'hostcpuids', 'hddbackends', 'hdds', 'dvds', 'floppies', 'usbhost',
        'usbfilters', 'systemproperties', 'extpacks', 'groups', 'webcams',
        'screenshotformats'
    )

    if item not in types:
        raise CommandExecutionError(
            'Item must be one of: {0}.'.format(', '.join(types))
        )

    flag = ''
    if details is True:
        flag = ' -l'

    ret = {}
    tmp_id = None
    tmp_dict = {}
    cmd = '{0} list{1} {2}'.format(vboxcmd(), flag, item)
    for line in salt.modules.cmdmod.run(cmd).splitlines():
        if not line.strip():
            continue
        comps = line.split(':')
        if len(comps) < 1:
            continue
        if tmp_id is not None:
            ret[tmp_id] = tmp_dict
        line_val = ':'.join(comps[1:]).strip()
        if comps[0] == group_by:
            tmp_id = line_val
            tmp_dict = {}
        tmp_dict[comps[0]] = line_val
    return ret
