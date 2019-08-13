# -*- coding: utf-8 -*-
'''
States for managing zpools

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs, salt.modules.zpool
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: 2016.3.0
.. versionchanged:: 2018.3.1
  Big refactor to remove duplicate code, better type converions and improved
  consistancy in output.

.. code-block:: yaml

    oldpool:
      zpool.absent:
        - export: true

    newpool:
      zpool.present:
        - config:
            import: false
            force: true
        - properties:
            comment: salty storage pool
        - layout:
            - mirror:
              - /dev/disk0
              - /dev/disk1
            - mirror:
              - /dev/disk2
              - /dev/disk3

    partitionpool:
      zpool.present:
        - config:
            import: false
            force: true
        - properties:
            comment: disk partition salty storage pool
            ashift: '12'
            feature@lz4_compress: enabled
        - filesystem_properties:
            compression: lz4
            atime: on
            relatime: on
        - layout:
            - /dev/disk/by-uuid/3e43ce94-77af-4f52-a91b-6cdbb0b0f41b

    simplepool:
      zpool.present:
        - config:
            import: false
            force: true
        - properties:
            comment: another salty storage pool
        - layout:
            - /dev/disk0
            - /dev/disk1

.. warning::

    The layout will never be updated, it will only be used at time of creation.
    It's a whole lot of work to figure out if a devices needs to be detached, removed,
    etc. This is best done by the sysadmin on a case per case basis.

    Filesystem properties are also not updated, this should be managed by the zfs state module.

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
from collections import namedtuple
import itertools
import os
import logging

# Import Salt libs
from salt.utils.odict import OrderedDict
from salt.ext.six import iteritems

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'zpool'


def __virtual__():
    '''
    Provides zpool state
    '''
    if __grains__.get('zfs_support'):
        return __virtualname__
    else:
        return False, 'The zpool state cannot be loaded: zfs not supported'


def _layout_to_vdev(layout, device_dir=None):
    '''
    Turn the layout data into usable vdevs spedcification

    We need to support 2 ways of passing the layout:

    .. code::
        layout_new:
          - mirror:
            - disk0
            - disk1
          - mirror:
            - disk2
            - disk3

    .. code:
        layout_legacy:
          mirror-0:
            disk0
            disk1
          mirror-1:
            disk2
            disk3

    '''
    vdevs = []

    # NOTE: check device_dir exists
    if device_dir and not os.path.exists(device_dir):
        device_dir = None

    # NOTE: handle list of OrderedDicts (new layout)
    if isinstance(layout, list):
        # NOTE: parse each vdev as a tiny layout and just append
        for vdev in layout:
            if isinstance(vdev, OrderedDict):
                vdevs.extend(_layout_to_vdev(vdev, device_dir))
            else:
                if device_dir and vdev[0] != '/':
                    vdev = os.path.join(device_dir, vdev)
                vdevs.append(vdev)

    # NOTE: handle nested OrderedDict (legacy layout)
    #       this is also used to parse the nested OrderedDicts
    #       from the new layout
    elif isinstance(layout, OrderedDict):
        for vdev in layout:
            # NOTE: extract the vdev type and disks in the vdev
            vdev_type = vdev.split('-')[0]
            vdev_disk = layout[vdev]

            # NOTE: skip appending the dummy type 'disk'
            if vdev_type != 'disk':
                vdevs.append(vdev_type)

            # NOTE: ensure the disks are a list (legacy layout are not)
            if not isinstance(vdev_disk, list):
                vdev_disk = vdev_disk.split(' ')

            # NOTE: also append the actualy disks behind the type
            #       also prepend device_dir to disks if required
            for disk in vdev_disk:
                if device_dir and disk[0] != '/':
                    disk = os.path.join(device_dir, disk)
                vdevs.append(disk)

    # NOTE: we got invalid data for layout
    else:
        vdevs = None

    return vdevs


StateResult = namedtuple('StateResult', ['result', 'comment', 'changes'])


def _state_exec(zpool, fn, comment, test_comment, fail_comment, result_key, changes):
    if __opts__['test']:
        return StateResult(None, test_comment, {})
    mod_res = fn()
    if not mod_res[result_key]:
        return StateResult(
            False, '{}:\n{}'.format(fail_comment,
                                    mod_res.get('error', '(Unknown error)')), {})
    return StateResult(True, comment, changes)


CreateZPoolParams = namedtuple('CreateZPoolParams', ['name', 'vdevs_args'])
PresentChanges = namedtuple(
    'PresentChanges',
    ['create_zpool', 'set_properties', 'set_fs_properties', 'cur_properties'])


def _calc_property_changes(zpool, properties, filesystem_properties):
    set_props = {}
    set_fs_props = {}
    cur_props = __salt__['zpool.get'](zpool, parsable=True)

    for prop_key, want_val in itertools.chain(iteritems(properties),
                                              iteritems(filesystem_properties)):
        if prop_key not in cur_props:
            log.warning('zpool property "%s" does not exist', prop_key)
        elif cur_props[prop_key] != want_val:
            set_props[prop_key] = want_val
        else:
            log.debug('zpool property "%s" is up-to-date (value is %s)', prop_key,
                      want_val)

    return cur_props, set_props, set_fs_props


def _calc_present_changes(name, props, fs_props, layout, config):
    """
    Calculate what changes are needed to get the given zpool into the requested state
    """
    if not __salt__['zpool.exists'](name):
        # Create and set the properties in one pass
        vdevs_args = _layout_to_vdev(layout, config['device_dir'])
        return PresentChanges(
            create_zpool=CreateZPoolParams(name, vdevs_args),
            set_properties=props,
            set_fs_properties=fs_props,
            cur_properties={},
        )

    # Zpool exists: Check what properties need to be updated
    cur_props, set_props, set_fs_props = _calc_property_changes(name, props, fs_props)

    return PresentChanges(create_zpool=None,
                          set_properties=set_props,
                          set_fs_properties=set_fs_props,
                          cur_properties=cur_props)


def _create_zpool(changes, config):
    name = changes.create_zpool.name

    if __opts__['test']:
        return StateResult(None, 'zpool will be created', {})

    if config['import']:
        fn = lambda: __salt__['zpool.import'](
            name, force=config['force'], import_dirs=config['import_dirs'])
        res = _state_exec(name,
                          fn,
                          comment='zpool was imported',
                          test_comment='[unseen]',
                          fail_comment='[unseen]',
                          result_key='imported',
                          changes={'imported': name})

        if res.result:
            return res

        # Fall-through: zpool was not imported

    if not changes.create_zpool.vdevs_args:
        return StateResult(
            False,
            'zpool could not be imported and no (valid) layout was specified to create it',
            {})

    create_args = (name, ) + tuple(changes.create_zpool.vdevs_args)
    mod_res = __salt__['zpool.create'](*create_args,
                                       force=config['force'],
                                       properties=changes.set_properties,
                                       filesysytem_properties=changes.set_fs_properties)
    all_props = dict(
        itertools.chain(iteritems(changes.set_properties),
                        iteritems(changes.set_fs_properties)))

    ok = mod_res['created']
    err_msg = 'Failed to create zpool:\n{}'.format(
        mod_res.get('error', '(Unknown error)'))
    return StateResult(
        ok,
        'zpool was created' if ok else err_msg,
        {} if not ok else {
            'created': name,
            'properties': all_props,
        },
    )


def _update_zpool(name, changes, config):
    if not changes.set_properties and not changes.set_fs_properties:
        # No property changes needed
        return True, 'zpool is up-to-date', {}

    if __opts__['test']:
        return None, 'Properties will be updated', {}

    prop_changes = {}
    set_args = []
    for key, val in itertools.chain(iteritems(changes.set_properties),
                                    iteritems(changes.set_fs_properties)):
        prev = changes.cur_properties[key]
        log.info('Update zpool property %s : %s -> %s', key, prev, val)
        mod_res = __salt__['zpool.set'](name, key, val)
        if not mod_res['set']:
            return False, 'Failed to update "{}" property "{}":\n'.format(
                key, mod_res['error']), prop_changes
        prop_changes[key] = {
            'old': prev,
            'new': val,
        }

    return True, 'Properties updated', prop_changes


def present(name, properties=None, filesystem_properties=None, layout=None,
            config=None):
    '''
    ensure storage pool is present on the system

    name : string
        name of storage pool
    properties : dict
        optional set of properties to set for the storage pool
    filesystem_properties : dict
        optional set of filesystem properties to set for the storage pool (creation only)
    layout: dict
        disk layout to use if the pool does not exist (creation only)
    config : dict
        fine grain control over this state

    .. note::

        The following configuration properties can be toggled in the config parameter.
          - import (true) - try to import the pool before creating it if absent
          - import_dirs (None) - specify additional locations to scan for devices on import (comma-seperated)
          - device_dir (None, SunOS=/dev/dsk, Linux=/dev) - specify device directory to prepend for none
            absolute device paths
          - force (false) - try to force the import or creation

    .. note::

        It is no longer needed to give a unique name to each top-level vdev, the old
        layout format is still supported but no longer recommended.

        .. code-block:: yaml

            - mirror:
              - /tmp/vdisk3
              - /tmp/vdisk2
            - mirror:
              - /tmp/vdisk0
              - /tmp/vdisk1

        The above yaml will always result in the following zpool create:

        .. code-block:: bash

            zpool create mypool mirror /tmp/vdisk3 /tmp/vdisk2 mirror /tmp/vdisk0 /tmp/vdisk1

    .. warning::

        The legacy format is also still supported but not recommended,
        because ID's inside the layout dict must be unique they need to have a suffix.

        .. code-block:: yaml

            mirror-0:
              /tmp/vdisk3
              /tmp/vdisk2
            mirror-1:
              /tmp/vdisk0
              /tmp/vdisk1

    .. warning::

        Pay attention to the order of your dict!

        .. code-block:: yaml

            - mirror:
              - /tmp/vdisk0
              - /tmp/vdisk1
            - /tmp/vdisk2

        The above will result in the following zpool create:

        .. code-block:: bash

            zpool create mypool mirror /tmp/vdisk0 /tmp/vdisk1 /tmp/vdisk2

        Creating a 3-way mirror! While you probably expect it to be mirror
        root vdev with 2 devices + a root vdev of 1 device!

    '''
    # config defaults
    default_config = {
        'import': True,
        'import_dirs': None,
        'device_dir': {
            'SunOS': '/dev/dsk',
            'Linux': '/dev',
        }.get(__grains__['kernel']),
        'force': False,
    }

    # Apply a default config
    default_config.update(config or {})
    config = default_config

    # ensure properties are zfs values
    properties = __utils__['zfs.from_auto_dict'](properties or {})
    filesystem_properties = __utils__['zfs.from_auto_dict'](filesystem_properties or {})

    # Calc and apply the pending changes
    pending_changes = _calc_present_changes(name, properties, filesystem_properties,
                                            layout, config)
    if pending_changes.create_zpool:
        tup = _create_zpool(pending_changes, config)
    else:
        tup = _update_zpool(name, pending_changes, config)

    result, comment, changes = tup
    return {
        'name': name,
        'result': result,
        'comment': comment,
        'changes': changes,
    }


AbsentChanges = namedtuple('AbsentChanges', ('force', 'export_pool', 'destroy_pool'))


def _calc_absent_changes(name, export, force):
    exists = __salt__['zpool.exists'](name)
    if not exists:
        # Nothing to do
        return AbsentChanges(force, None, None)
    elif export:
        return AbsentChanges(force, export_pool=name, destroy_pool=None)
    else:
        return AbsentChanges(force, export_pool=None, destroy_pool=name)


def _apply_absent(name, changes):
    if changes.destroy_pool is None and changes.export_pool is None:
        # No changes to make to the zpool.
        return True, 'zpool is absent', {}

    assert not (changes.export_pool
                and changes.destroy_pool), 'Cannot both destroy AND export pool'

    # Destroy/export are very similar, so we can get away with just building
    # some strings to pass to the underlying code
    verb = 'export' if changes.export_pool else 'destroy'
    past = verb + 'ed'
    fn = 'zpool.{v}'.format(v=verb)
    return _state_exec(name,
                       lambda: __salt__[fn](name, force=changes.force),
                       comment='zpool was {}'.format(past),
                       test_comment='zpool will be {}'.format(past),
                       fail_comment='Failed to {} zpool'.format(verb),
                       result_key=past,
                       changes={past: name})


def absent(name, export=False, force=False):
    '''
    ensure storage pool is absent on the system

    name : string
        name of storage pool
    export : boolean
        export instread of destroy the zpool if present
    force : boolean
        force destroy or export

    '''
    pending_changes = _calc_absent_changes(name, export, force)

    result, comment, changes = _apply_absent(name, pending_changes)
    return {
        'name': name,
        'result': result,
        'comment': comment,
        'changes': changes,
    }


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
