# -*- coding: utf-8 -*-
'''
Management zfs datasets

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       zfs
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: Boron

.. code-block:: yaml

    TODO: add example here

'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
from salt.utils.odict import OrderedDict

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
            '{0} state module can only be loaded on illumos, Solaris, SmartOS, FreeBSD, ...'.format(
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
    name = name.lower()
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
        if name in __salt__['zfs.list'](name, **{'type': dataset_type}):  # we need to destroy it
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

        If a volume with ``name`` exists, this state will succeed without
        destroying the volume specified by ``name``. This module is dataset type sensitive.

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

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
