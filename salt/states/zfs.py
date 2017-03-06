# -*- coding: utf-8 -*-
'''
Management zfs datasets

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       zfs
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: 2016.3.0

.. code-block:: yaml

    test/shares/yuki:
      zfs.filesystem_present:
        - create_parent: true
        - properties:
            quota: 16G

    test/iscsi/haruhi:
      zfs.volume_present:
        - create_parent: true
        - volume_size: 16M
        - sparse: true
        - properties:
            readonly: on

    test/shares/yuki@frozen:
      zfs.snapshot_present

    moka_origin:
      zfs.hold_present
        - snapshot: test/shares/yuki@frozen

    test/shares/moka:
      zfs.filesystem_present:
        - cloned_from: test/shares/yuki@frozen

    test/shares/moka@tsukune:
      zfs.snapshot_absent

'''
from __future__ import absolute_import

# Import Python libs
import logging
from time import strftime, strptime, gmtime

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'zfs'


def __virtual__():
    '''
    Provides zfs state
    '''
    if 'zfs.create' in __salt__:
        return True
    else:
        return (
            False,
            '{0} state module can only be loaded on illumos, Solaris, SmartOS, FreeBSD, Linux, ...'.format(
                __virtualname__
            )
        )


def _absent(name, dataset_type, force=False, recursive=False):
    '''
    internal shared function for *_absent

    name : string
        name of dataset
    dataset_type : string [filesystem, volume, snapshot, or bookmark]
        type of dataset to remove
    force : boolean
        try harder to destroy the dataset
    recursive : boolean
        also destroy all the child datasets

    '''
    dataset_type = dataset_type.lower()
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.{0}_absent::{1}::config::force = {2}'.format(dataset_type, name, force))
    log.debug('zfs.{0}_absent::{1}::config::recursive = {2}'.format(dataset_type, name, recursive))

    # check name and type
    if dataset_type not in ['filesystem', 'volume', 'snapshot', 'bookmark']:
        ret['result'] = False
        ret['comment'] = 'unknown dateset type: {0}'.format(dataset_type)

    if ret['result'] and dataset_type in ['snapshot'] and '@' not in name:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(name)

    if ret['result'] and dataset_type in ['bookmark'] and '#' not in name:
        ret['result'] = False
        ret['comment'] = 'invalid bookmark name: {0}'.format(name)

    if ret['result'] and dataset_type in ['filesystem', 'volume']:
        if '@' in name or '#' in name:
            ret['result'] = False
            ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    # check if dataset exists
    if ret['result']:
        dataset = name if '#' not in name else None  # work around bookmark oddities
        if name in __salt__['zfs.list'](dataset, **{'type': dataset_type}):  # we need to destroy it
            result = {name: 'destroyed'}
            if not __opts__['test']:
                result = __salt__['zfs.destroy'](name, **{'force': force, 'recursive': recursive})

            ret['result'] = name in result and result[name] == 'destroyed'
            ret['changes'] = result if ret['result'] else {}
            if ret['result']:
                ret['comment'] = '{0} {1} was destroyed'.format(
                    dataset_type,
                    name
                )
            else:
                ret['comment'] = 'failed to destroy {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]
        else:  # dataset with type and name does not exist! (all good)
            ret['comment'] = '{0} {1} is not present'.format(
                dataset_type,
                name
            )

    return ret


def filesystem_absent(name, force=False, recursive=False):
    '''
    ensure filesystem is absent on the system

    name : string
        name of filesystem
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    ..warning:

        If a volume with ``name`` exists, this state will succeed without
        destroying the volume specified by ``name``. This module is dataset type sensitive.

    '''
    return _absent(name, 'filesystem', force, recursive)


def volume_absent(name, force=False, recursive=False):
    '''
    ensure volume is absent on the system

    name : string
        name of volume
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)

    ..warning:

        If a filesystem with ``name`` exists, this state will succeed without
        destroying the filesystem specified by ``name``. This module is dataset type sensitive.

    '''
    return _absent(name, 'volume', force, recursive)


def snapshot_absent(name, force=False, recursive=False):
    '''
    ensure snapshot is absent on the system

    name : string
        name of snapshot
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)
    '''
    return _absent(name, 'snapshot', force, recursive)


def bookmark_absent(name, force=False, recursive=False):
    '''
    ensure bookmark is absent on the system

    name : string
        name of snapshot
    force : boolean
        try harder to destroy the dataset (zfs destroy -f)
    recursive : boolean
        also destroy all the child datasets (zfs destroy -r)
    '''
    return _absent(name, 'bookmark', force, recursive)


def hold_absent(name, snapshot, recursive=False):
    '''
    ensure hold is absent on the system

    name : string
        name of holdt
    snapshot : string
        name of snapshot
    recursive : boolean
        recursively releases a hold with the given tag on the snapshots of all descendent file systems.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.hold_absent::{0}::config::snapshot = {1}'.format(name, snapshot))
    log.debug('zfs.hold_absent::{0}::config::recursive = {1}'.format(name, recursive))

    # check name and type
    if '@' not in snapshot:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(snapshot)

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid tag name: {0}'.format(name)

    if ret['result']:
        result = __salt__['zfs.holds'](snapshot)
        if snapshot not in result:
            ret['result'] = False
            ret['comment'] = '{0} is probably not a snapshot'.format(snapshot)
        else:
            if snapshot in result[snapshot]:
                ret['result'] = False
                ret['comment'] = result[snapshot]
            elif result[snapshot] == 'no holds' or name not in result[snapshot]:
                ret['comment'] = 'hold {0} not present'.format(name)
            else:
                result = {snapshot: {name: 'released'}}
                if not __opts__['test']:
                    result = __salt__['zfs.release'](name, snapshot, **{'recursive': recursive})

                ret['result'] = snapshot in result and name in result[snapshot]
                if ret['result']:
                    ret['changes'] = result[snapshot]
                    ret['comment'] = 'hold {0} released'.format(name)
                else:
                    ret['comment'] = 'failed to release {0}'.format(name)
                    if snapshot in result:
                        ret['comment'] = result[snapshot]

    return ret


def hold_present(name, snapshot, recursive=False):
    '''
    ensure hold is present on the system

    name : string
        name of holdt
    snapshot : string
        name of snapshot
    recursive : boolean
        recursively add hold with the given tag on the snapshots of all descendent file systems.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.hold_present::{0}::config::snapshot = {1}'.format(name, snapshot))
    log.debug('zfs.hold_present::{0}::config::recursive = {1}'.format(name, recursive))

    # check name and type
    if '@' not in snapshot:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(snapshot)

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid tag name: {0}'.format(name)

    if ret['result']:
        result = __salt__['zfs.holds'](snapshot)
        if snapshot not in result:
            ret['result'] = False
            ret['comment'] = '{0} is probably not a snapshot'.format(snapshot)
        else:
            if snapshot in result[snapshot]:
                ret['result'] = False
                ret['comment'] = result[snapshot]
            elif result[snapshot] == 'no holds' or name not in result[snapshot]:  # add hold
                result = {snapshot: {name: 'held'}}
                if not __opts__['test']:
                    result = __salt__['zfs.hold'](name, snapshot, **{'recursive': recursive})

                ret['result'] = snapshot in result and name in result[snapshot]
                if ret['result']:
                    ret['changes'] = result[snapshot]
                    ret['comment'] = 'hold {0} added to {1}'.format(name, snapshot)
                else:
                    ret['comment'] = 'failed to add hold {0}'.format(name)
                    if snapshot in result:
                        ret['comment'] = result[snapshot]
            else:  # hold present
                ret['comment'] = 'hold already exists'

    return ret


def filesystem_present(name, create_parent=False, properties=None, cloned_from=None):
    '''
    ensure filesystem exists and has properties set

    name : string
        name of filesystem
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    cloned_from : string
        name of snapshot to clone
    properties : dict
        additional zfs properties (-o)

    .. note::
        ``cloned_from`` is only use if the filesystem does not exist yet,
        when ``cloned_from`` is set after the filesystem exists it will be ignored.

    .. note::
        Properties do not get cloned, if you specify the properties in the
        state file they will be applied on a subsequent run.

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check params
    if not properties:
        properties = {}

    log.debug('zfs.filesystem_present::{0}::config::create_parent = {1}'.format(name, create_parent))
    log.debug('zfs.filesystem_present::{0}::config::cloned_from = {1}'.format(name, cloned_from))
    log.debug('zfs.filesystem_present::{0}::config::properties = {1}'.format(name, properties))

    for prop in properties:  # salt breaks the on/off/yes/no properties
        if isinstance(properties[prop], bool):
            properties[prop] = 'on' if properties[prop] else 'off'

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    if cloned_from:
        cloned_parent = cloned_from[:cloned_from.index('@')]
        if '@' not in cloned_from:
            ret['result'] = False
            ret['comment'] = '{0} is not a snapshot'.format(cloned_from)
        elif cloned_from not in __salt__['zfs.list'](cloned_from, **{'type': 'snapshot'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} does not exist'.format(cloned_from)
        elif cloned_parent not in __salt__['zfs.list'](cloned_parent, **{'type': 'filesystem'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} is not from a filesystem'.format(cloned_from)

    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': 'filesystem'}):  # update properties if needed
            result = {}
            if len(properties) > 0:
                result = __salt__['zfs.get'](name, **{'properties': ','.join(properties.keys()), 'fields': 'value', 'depth': 1})

            for prop in properties:
                if properties[prop] != result[name][prop]['value']:
                    if name not in ret['changes']:
                        ret['changes'][name] = {}
                    ret['changes'][name][prop] = properties[prop]

            if len(ret['changes']) > 0:
                if not __opts__['test']:
                    result = __salt__['zfs.set'](name, **ret['changes'][name])
                    if name not in result:
                        ret['result'] = False
                    else:
                        for prop in result[name]:
                            if result[name][prop] != 'set':
                                ret['result'] = False

                if ret['result']:
                    ret['comment'] = 'filesystem {0} was updated'.format(name)
                else:
                    ret['changes'] = {}
                    ret['comment'] = 'filesystem {0} failed to be updated'.format(name)
            else:
                ret['comment'] = 'filesystem {0} is up to date'.format(name)
        else:  # create filesystem
            result = {name: 'created'}
            if not __opts__['test']:
                if not cloned_from:
                    result = __salt__['zfs.create'](name, **{'create_parent': create_parent, 'properties': properties})
                else:
                    result = __salt__['zfs.clone'](cloned_from, name, **{'create_parent': create_parent, 'properties': properties})

            ret['result'] = name in result
            if ret['result']:
                ret['result'] = result[name] == 'created' or result[name].startswith('cloned')
            if ret['result']:
                ret['changes'][name] = properties if len(properties) > 0 else result[name]
                ret['comment'] = 'filesystem {0} was created'.format(name)
            else:
                ret['comment'] = 'failed to create filesystem {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]
    return ret


def volume_present(name, volume_size, sparse=False, create_parent=False, properties=None, cloned_from=None):
    '''
    ensure volume exists and has properties set

    name : string
        name of volume
    volume_size : string
        size of volume
    sparse : boolean
        create sparse volume
    create_parent : boolean
        creates all the non-existing parent datasets.
        any property specified on the command line using the -o option is ignored.
    cloned_from : string
        name of snapshot to clone
    properties : dict
        additional zfs properties (-o)

    .. note::
        ``cloned_from`` is only use if the volume does not exist yet,
        when ``cloned_from`` is set after the volume exists it will be ignored.

    .. note::
        Properties do not get cloned, if you specify the properties in the state file
        they will be applied on a subsequent run.

        ``volume_size`` is considered a property, so the volume's size will be
        corrected when the properties get updated if it differs from the
        original volume.

        The sparse parameter is ignored when using ``cloned_from``.

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check params
    if not properties:
        properties = {}

    log.debug('zfs.volume_present::{0}::config::volume_size = {1}'.format(name, volume_size))
    log.debug('zfs.volume_present::{0}::config::sparse = {1}'.format(name, sparse))
    log.debug('zfs.volume_present::{0}::config::create_parent = {1}'.format(name, create_parent))
    log.debug('zfs.volume_present::{0}::config::cloned_from = {1}'.format(name, cloned_from))
    log.debug('zfs.volume_present::{0}::config::properties = {1}'.format(name, properties))

    for prop in properties:  # salt breaks the on/off/yes/no properties
        if isinstance(properties[prop], bool):
            properties[prop] = 'on' if properties[prop] else 'off'

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    if cloned_from:
        cloned_parent = cloned_from[:cloned_from.index('@')]
        if '@' not in cloned_from:
            ret['result'] = False
            ret['comment'] = '{0} is not a snapshot'.format(cloned_from)
        elif cloned_from not in __salt__['zfs.list'](cloned_from, **{'type': 'snapshot'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} does not exist'.format(cloned_from)
        elif cloned_parent not in __salt__['zfs.list'](cloned_parent, **{'type': 'volume'}):
            ret['result'] = False
            ret['comment'] = 'snapshot {0} is not from a volume'.format(cloned_from)

    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': 'volume'}):  # update properties if needed
            properties['volsize'] = volume_size  # add volume_size to properties
            result = __salt__['zfs.get'](name, **{'properties': ','.join(properties.keys()), 'fields': 'value', 'depth': 1})

            for prop in properties:
                if properties[prop] != result[name][prop]['value']:
                    if name not in ret['changes']:
                        ret['changes'][name] = {}
                    ret['changes'][name][prop] = properties[prop]

            if len(ret['changes']) > 0:
                if not __opts__['test']:
                    result = __salt__['zfs.set'](name, **ret['changes'][name])
                    if name not in result:
                        ret['result'] = False
                    else:
                        for prop in result[name]:
                            if result[name][prop] != 'set':
                                ret['result'] = False

                if ret['result']:
                    ret['comment'] = 'volume {0} was updated'.format(name)
                else:
                    ret['changes'] = {}
                    ret['comment'] = 'volume {0} failed to be updated'.format(name)
            else:
                ret['comment'] = 'volume {0} is up to date'.format(name)
        else:  # create volume
            result = {name: 'created'}
            if not __opts__['test']:
                if not cloned_from:
                    result = __salt__['zfs.create'](name, **{
                        'volume_size': volume_size,
                        'sparse': sparse,
                        'create_parent': create_parent,
                        'properties': properties
                    })
                else:
                    result = __salt__['zfs.clone'](cloned_from, name, **{'create_parent': create_parent, 'properties': properties})

            ret['result'] = name in result
            if ret['result']:
                ret['result'] = result[name] == 'created' or result[name].startswith('cloned')
            if ret['result']:
                ret['changes'][name] = properties if len(properties) > 0 else result[name]
                ret['comment'] = 'volume {0} was created'.format(name)
            else:
                ret['comment'] = 'failed to create volume {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]
    return ret


def bookmark_present(name, snapshot):
    '''
    ensure bookmark exists

    name : string
        name of bookmark
    snapshot : string
        name of snapshot

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    log.debug('zfs.bookmark_present::{0}::config::snapshot = {1}'.format(name, snapshot))

    if '@' not in snapshot:
        ret['result'] = False
        ret['comment'] = '{0} is not a snapshot'.format(snapshot)

    if '#' not in name:
        if '/' not in name:
            name = '{0}#{1}'.format(snapshot[:snapshot.index('@')], name)
        else:
            ret['result'] = False
            ret['comment'] = '{0} is not a bookmark'.format(name)

    if ret['result']:
        if name in __salt__['zfs.list'](**{'type': 'bookmark'}):
            ret['comment'] = 'bookmark already exists'
        else:  # create bookmark
            result = {snapshot: 'bookmarked'}
            if not __opts__['test']:
                result = __salt__['zfs.bookmark'](snapshot, name)

            ret['result'] = snapshot in result and result[snapshot].startswith('bookmarked')
            if ret['result']:
                ret['changes'] = result
                ret['comment'] = 'snapshot {0} was bookmarked as {1}'.format(snapshot, name)
            else:
                ret['comment'] = 'failed to create bookmark {0}'.format(name)
    return ret


def snapshot_present(name, recursive=False, properties=None):
    '''
    ensure snapshot exists and has properties set

    name : string
        name of snapshot
    recursive : boolean
        recursively create snapshots of all descendent datasets
    properties : dict
        additional zfs properties (-o)

    .. note:
        Properties are only set at creation time

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check params
    if not properties:
        properties = {}

    log.debug('zfs.snapshot_present::{0}::config::recursive = {1}'.format(name, recursive))
    log.debug('zfs.snapshot_present::{0}::config::properties = {1}'.format(name, properties))

    for prop in properties:  # salt breaks the on/off/yes/no properties
        if isinstance(properties[prop], bool):
            properties[prop] = 'on' if properties[prop] else 'off'

    if '@' not in name:
        ret['result'] = False
        ret['comment'] = 'invalid snapshot name: {0}'.format(name)

    if ret['result']:
        if name in __salt__['zfs.list'](name, **{'type': 'snapshot'}):  # we are all good
            ret['comment'] = 'snapshot already exists'
        else:  # create snapshot
            result = {name: 'snapshotted'}
            if not __opts__['test']:
                result = __salt__['zfs.snapshot'](name, **{'recursive': recursive, 'properties': properties})

            ret['result'] = name in result and result[name] == 'snapshotted'
            if ret['result']:
                ret['changes'][name] = properties if len(properties) > 0 else result[name]
                ret['comment'] = 'snapshot {0} was created'.format(name)
            else:
                ret['comment'] = 'failed to create snapshot {0}'.format(name)
                if name in result:
                    ret['comment'] = result[name]

    return ret


def promoted(name):
    '''
    ensure a dataset is not a clone

    name : string
        name of fileset or volume

    ..warning::

        only one dataset can be the origin,
        if you promote a clone the original will now point to the promoted dataset

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if '@' in name or '#' in name:
        ret['result'] = False
        ret['comment'] = 'invalid filesystem or volume name: {0}'.format(name)

    if ret['result']:
        if name in __salt__['zfs.list'](name):
            origin = '-'
            if not __opts__['test']:
                origin = __salt__['zfs.get'](name, **{'properties': 'origin', 'fields': 'value'})[name]['origin']['value']

            if origin == '-':
                ret['comment'] = '{0} already promoted'.format(name)
            else:
                result = {name: 'promoted'}
                if not __opts__['test']:
                    result = __salt__['zfs.promote'](name)

                ret['result'] = name in result and result[name] == 'promoted'
                ret['changes'] = result if ret['result'] else {}
                if ret['result']:
                    ret['comment'] = '{0} was promoted'.format(name)
                else:
                    ret['comment'] = 'failed to promote {0}'.format(name)
                    if name in result:
                        ret['comment'] = result[name]

        else:  # we don't have the dataset
            ret['result'] = False
            ret['comment'] = 'dataset {0} does not exist'.format(name)

    return ret


def scheduled_snapshot(name, prefix, recursive=True, schedule=None):
    '''
    maintain a set of snapshots based on a schedule

    name : string
        name of filesystem or volume
    prefix : string
        prefix for the snapshots
        e.g. 'test' will result in snapshots being named 'test-YYYYMMDD_HHMM'
    recursive : boolean
        create snapshots for all children also
    schedule : dict
        dict holding the schedule, the following keys are available (minute, hour,
        day, month, and year) by default all are set to 0 the value indicated the
        number of snapshots of that type to keep around.

    ..warning::

        snapshots will only be created and pruned every time the state runs.
        a schedule must be setup to automatically run the state. this means that if
        you run the state daily the hourly snapshot will only be made once per day!

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    ## parse parameters
    # update default schedule
    state_schedule = schedule if schedule else {}
    schedule = {
        'minute': 0,
        'hour': 0,
        'day': 0,
        'month': 0,
        'year': 0,
    }
    for hold in state_schedule:
        if hold not in schedule:
            del state_schedule[hold]
    schedule.update(state_schedule)
    # check name
    if name not in __salt__['zfs.list'](name, **{'type': 'filesystem'}) and name not in __salt__['zfs.list'](name, **{'type': 'volume'}):
        ret['comment'] = '{0} is not a filesystem or a volume or does not exist'.format(name)
        ret['result'] = False
    # check prefix
    if not prefix or len(prefix) < 4:
        ret['comment'] = 'prefix ({0}) must be at least 4 long'.format(prefix)
        ret['result'] = False
    # check schedule
    snap_count = 0
    for hold in schedule:
        if not isinstance(schedule[hold], int):
            ret['comment'] = 'schedule values must be integers'
            ret['result'] = False
            break
        snap_count += schedule[hold]
    if ret['result'] and snap_count == 0:
        ret['comment'] = 'at least one snapshot must be schedule'
        ret['result'] = False

    # print debug info
    log.debug('zfs.scheduled_snapshot::{0}::config::recursive = {1}'.format(name, recursive))
    log.debug('zfs.scheduled_snapshot::{0}::config::prefix = {1}'.format(name, prefix))
    log.debug('zfs.scheduled_snapshot::{0}::config::schedule = {1}'.format(name, schedule))

    ## manage snapshots
    if ret['result']:
        # retreive snapshots
        prunable = []
        snapshots = {}
        for key in schedule:
            snapshots[key] = []

        for snap in sorted(__salt__['zfs.list'](name, **{'recursive': True, 'depth': 1, 'type': 'snapshot'}).keys()):
            if '@' not in snap:
                continue

            snap_name = snap[snap.index('@')+1:]
            if snap_name.startswith('{0}-'.format(prefix)):
                holds = __salt__['zfs.holds'](snap)
                if snap not in holds or holds[snap] == 'no holds':
                    prunable.append(snap)
                    continue
                for hold in holds[snap]:
                    hold = hold.strip()
                    if hold not in snapshots.keys():
                        continue
                    snapshots[hold].append(snap)
        log.debug('zfs.scheduled_snapshot::{0}::snapshots = {1}'.format(name, snapshots))

        # create snapshot
        needed_holds = []
        current_timestamp = gmtime()
        for hold in snapshots:
            # check if we need need to consider hold
            if schedule[hold] == 0:
                continue

            # check we need a new snapshot for hold
            if len(snapshots[hold]) > 0:
                snapshots[hold].sort()
                timestamp = strptime(snapshots[hold][-1], '{0}@{1}-%Y%m%d_%H%M%S'.format(name, prefix))
                if hold == 'minute':
                    if current_timestamp.tm_min <= timestamp.tm_min and \
                       current_timestamp.tm_hour <= timestamp.tm_hour and \
                       current_timestamp.tm_mday <= timestamp.tm_mday and \
                       current_timestamp.tm_mon <= timestamp.tm_mon and \
                       current_timestamp.tm_year <= timestamp.tm_year:
                        continue
                elif hold == 'hour':
                    if current_timestamp.tm_hour <= timestamp.tm_hour and \
                       current_timestamp.tm_mday <= timestamp.tm_mday and \
                       current_timestamp.tm_mon <= timestamp.tm_mon and \
                       current_timestamp.tm_year <= timestamp.tm_year:
                        continue
                elif hold == 'day':
                    if current_timestamp.tm_mday <= timestamp.tm_mday and \
                       current_timestamp.tm_mon <= timestamp.tm_mon and \
                       current_timestamp.tm_year <= timestamp.tm_year:
                        continue
                elif hold == 'month':
                    if current_timestamp.tm_mon <= timestamp.tm_mon and \
                       current_timestamp.tm_year <= timestamp.tm_year:
                        continue
                elif hold == 'year':
                    if current_timestamp.tm_year <= timestamp.tm_year:
                        continue
                else:
                    log.debug('zfs.scheduled_snapshot::{0}::hold_unknown = {1}'.format(name, hold))

            # mark snapshot for hold as needed
            needed_holds.append(hold)

        snap_name = '{prefix}-{timestamp}'.format(
            prefix=prefix,
            timestamp=strftime('%Y%m%d_%H%M%S')
        )
        log.debug('zfs.scheduled_snapshot::{0}::needed_holds = {1}'.format(name, needed_holds))
        if len(needed_holds) > 0:
            snap = '{dataset}@{snapshot}'.format(dataset=name, snapshot=snap_name)
            res = __salt__['zfs.snapshot'](snap, **{'recursive': recursive})
            if snap not in res or res[snap] != 'snapshotted':  # something went wrong!
                ret['comment'] = 'error creating snapshot ({0})'.format(snap)
                ret['result'] = False

            for hold in needed_holds:
                if not ret['result']:
                    continue  # skip if snapshot failed
                res = __salt__['zfs.hold'](hold, snap, **{'recursive': recursive})
                if snap not in res or hold not in res[snap] or res[snap][hold] != 'held':
                    ret['comment'] = "{0}error adding hold ({1}) to snapshot ({2})".format(
                        "{0}\n".format(ret['comment']) if not ret['result'] else '',
                        hold,
                        snap
                    )
                    ret['result'] = False
                else:  # add new snapshot to lists (for pruning)
                    snapshots[hold].append(snap)

            if ret['result']:
                ret['comment'] = 'scheduled snapshots were updated'
                ret['changes']['created'] = [snap]
                ret['changes']['pruned'] = []

        # prune snapshots
        for hold in schedule:
            if hold not in snapshots.keys():
                continue
            while len(snapshots[hold]) > schedule[hold]:
                # pop oldest snapshot and release hold
                snap = snapshots[hold].pop(0)
                __salt__['zfs.release'](hold, snap, **{'recursive': recursive})
                # check if snapshot is prunable
                holds = __salt__['zfs.holds'](snap)
                if snap not in holds or holds[snap] == 'no holds':
                    prunable.append(snap)

        if len(prunable) > 0:
            for snap in prunable:  # destroy if hold free
                res = __salt__['zfs.destroy'](snap, **{'recursive': recursive})
                if snap not in res or res[snap] != 'destroyed':
                    ret['comment'] = "{0}error prunding snapshot ({1})".format(
                        "{0}\n".format(ret['comment']) if not ret['result'] else '',
                        snap
                    )
                    ret['result'] = False
                else:
                    ret['comment'] = 'scheduled snapshots were updated'
                    if 'created' not in ret['changes']:
                        ret['changes']['created'] = []
                    if 'pruned' not in ret['changes']:
                        ret['changes']['pruned'] = []
                    ret['changes']['pruned'].append(snap)

    if ret['result'] and ret['comment'] == '':
        ret['comment'] = 'scheduled snapshots are up to date'

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
