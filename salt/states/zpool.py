# -*- coding: utf-8 -*-
'''
Management zpool

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       zpool
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: 2016.3.0

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
            mirror-0:
              /dev/disk0
              /dev/disk1
            mirror-1:
              /dev/disk2
              /dev/disk3

.. warning::

    The layout will never be updated, it will only be used at time of creation.
    It's a whole lot of work to figure out if a devices needs to be detached, removed, ... this is best done by the sysadmin on a case per case basis.

    Filesystem properties are also not updated, this should be managed by the zfs state module.

'''
from __future__ import absolute_import

# Import Python libs
import os
import stat
import logging

# Import Salt libs
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'zpool'


def __virtual__():
    '''
    Provides zpool state
    '''
    if 'zpool.create' in __salt__:
        return True
    else:
        return (
            False,
            '{0} state module can only be loaded on illumos, Solaris, SmartOS, FreeBSD, ...'.format(
                __virtualname__
            )
        )


def _check_device(device, config):
    '''
    Check if device is present
    '''
    if '/' not in device and config['device_dir'] and os.path.exists(config['device_dir']):
        device = os.path.join(config['device_dir'], device)

    if not os.path.exists(device):
        return False, 'not present on filesystem'
    else:
        mode = os.stat(device).st_mode
        if not stat.S_ISBLK(mode) and not stat.S_ISREG(mode) and not stat.S_ISCHR(mode):
            return False, 'not a block device, a file vdev or character special device'

    return True, ''


def present(name, properties=None, filesystem_properties=None, layout=None, config=None):
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
          - import_dirs (None) - specify additional locations to scan for devices on import
          - device_dir (None, SunOS=/dev/rdsk) - specify device directory to use if not absolute path
          - force (false) - try to force the import or creation

    .. note::

        Because ID's inside the layout dict must be unique they need to have a suffix.

        .. code-block:: yaml

            mirror-0:
              /tmp/vdisk3
              /tmp/vdisk2
            mirror-1:
              /tmp/vdisk0
              /tmp/vdisk1

        The above yaml will always result in the following zpool create:

        .. code-block:: bash

            zpool create mypool mirror /tmp/vdisk3 /tmp/vdisk2 mirror /tmp/vdisk0 /tmp/vdisk1

    .. warning::

        Pay attention to the order of your dict!

        .. code-block:: yaml

            mirror-0:
              /tmp/vdisk0
              /tmp/vdisk1
            /tmp/vdisk2:

        The above will result in the following zpool create:

        .. code-block:: bash

            zpool create mypool mirror /tmp/vdisk0 /tmp/vdisk1 /tmp/vdisk2

        Creating a 3-way mirror! Why you probably expect it to be mirror root vdev with 2 devices + a root vdev of 1 device!

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # config defaults
    state_config = config if config else {}
    config = {
        'import': True,
        'import_dirs': None,
        'device_dir': None if __grains__['kernel'] != 'SunOS' else '/dev/rdsk',
        'force': False
    }
    config.update(state_config)
    log.debug('zpool.present::{0}::config - {1}'.format(name, config))

    # validate layout
    if layout:
        layout_valid = True
        layout_result = {}
        for root_dev in layout:
            if '-' in root_dev:
                if root_dev.split('-')[0] not in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3', 'spare']:
                    layout_valid = False
                    layout_result[root_dev] = 'not a valid vdev type'
                layout[root_dev] = layout[root_dev].keys() if isinstance(layout[root_dev], OrderedDict) else layout[root_dev].split(' ')

                for dev in layout[root_dev]:
                    dev_info = _check_device(dev, config)
                    if not dev_info[0]:
                        layout_valid = False
                        layout_result[root_dev] = {}
                        layout_result[root_dev][dev] = dev_info[1]
            else:
                dev_info = _check_device(root_dev, config)
                if not dev_info[0]:
                    layout_valid = False
                    layout_result[root_dev] = dev_info[1]

        if not layout_valid:
            ret['result'] = False
            ret['comment'] = "{0}".format(layout_result)
            return ret

        log.debug('zpool.present::{0}::layout - {1}'.format(name, layout))

    # ensure the pool is present
    ret['result'] = False
    if __salt__['zpool.exists'](name):  # update
        ret['result'] = True

        # retrieve current properties
        properties_current = __salt__['zpool.get'](name)[name]

        # figure out if updates needed
        properties_update = []
        for prop in properties:
            if prop not in properties_current:
                continue

            value = properties[prop]
            if isinstance(value, bool):
                value = 'on' if value else 'off'

            if properties_current[prop] != value:
                properties_update.append(prop)

        # update properties
        for prop in properties_update:
            value = properties[prop]
            res = __salt__['zpool.set'](name, prop, value)

            # also transform value so we match with the return
            if isinstance(value, bool):
                value = 'on' if value else 'off'
            elif ' ' in value:
                value = "'{0}'".format(value)

            # check return
            if name in res and prop in res[name] and res[name][prop] == value:
                if name not in ret['changes']:
                    ret['changes'][name] = {}
                ret['changes'][name].update(res[name])
            else:
                ret['result'] = False
                if ret['comment'] == '':
                    ret['comment'] = 'The following properties were not updated:'
                ret['comment'] = '{0} {1}'.format(ret['comment'], prop)

        if ret['result']:
            ret['comment'] = 'properties updated' if len(ret['changes']) > 0 else 'no update needed'

    else:  # import or create
        if config['import']:  # try import
            log.debug('zpool.present::{0}::importing'.format(name))
            ret['result'] = __salt__['zpool.import'](
                name,
                force=config['force'],
                dir=config['import_dirs']
            )
            ret['result'] = ret['result'].get(name) == 'imported'
            if ret['result']:
                ret['changes'][name] = 'imported'
                ret['comment'] = 'storage pool {0} was imported'.format(name)

        if not ret['result']:  # create
            if not layout:
                ret['comment'] = 'storage pool {0} was not imported, no layout specified for creation'.format(name)
            else:
                log.debug('zpool.present::{0}::creating'.format(name))
                if __opts__['test']:
                    ret['result'] = True
                else:
                    # construct *vdev parameter for zpool.create
                    params = []
                    params.append(name)
                    for root_dev in layout:
                        if '-' in root_dev:  # special device
                            params.append(root_dev.split('-')[0])  # add the type by stripping the ID
                            if root_dev.split('-')[0] in ['mirror', 'log', 'cache', 'raidz1', 'raidz2', 'raidz3', 'spare']:
                                for sub_dev in layout[root_dev]:  # add all sub devices
                                    if '/' not in sub_dev and config['device_dir'] and os.path.exists(config['device_dir']):
                                        sub_dev = os.path.join(config['device_dir'], sub_dev)
                                    params.append(sub_dev)
                        else:  # normal device
                            if '/' not in root_dev and config['device_dir'] and os.path.exists(config['device_dir']):
                                root_dev = os.path.join(config['device_dir'], root_dev)
                            params.append(root_dev)

                    # execute zpool.create
                    ret['result'] = __salt__['zpool.create'](*params, force=config['force'], properties=properties, filesystem_properties=filesystem_properties)
                    if ret['result'].get(name) == 'created':
                        ret['result'] = True
                    else:
                        if ret['result'].get(name):
                            ret['comment'] = ret['result'][name]
                        ret['result'] = False

                if ret['result']:
                    ret['changes'][name] = 'created'
                    ret['comment'] = 'storage pool {0} was created'.format(name)

    return ret


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
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # config defaults
    log.debug('zpool.absent::{0}::config::force = {1}'.format(name, force))
    log.debug('zpool.absent::{0}::config::export = {1}'.format(name, export))

    # ensure the pool is absent
    if __salt__['zpool.exists'](name):  # looks like we need to do some work
        ret['result'] = False

        if export:  # try to export the zpool
            if __opts__['test']:
                ret['result'] = True
            else:
                ret['result'] = __salt__['zpool.export'](name, force=force)
                ret['result'] = ret['result'].get(name) == 'exported'

        else:  # try to destroy the zpool
            if __opts__['test']:
                ret['result'] = True
            else:
                ret['result'] = __salt__['zpool.destroy'](name, force=force)
                ret['result'] = ret['result'].get(name) == 'destroyed'

        if ret['result']:  # update the changes and comment
            ret['changes'][name] = 'exported' if export else 'destroyed'
            ret['comment'] = 'storage pool {0} was {1}'.format(name, ret['changes'][name])

    else:  # we are looking good
        ret['result'] = True
        ret['comment'] = 'storage pool {0} is absent'.format(name)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
