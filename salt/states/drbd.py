# -*- coding: utf-8 -*-
'''
State module to provide DRBD functionality to Salt

.. versionadded:: neon

:maintainer:    Nick Wang <nwang@suse.com>
:maturity:      alpha
:depends:       None
:platform:      Linux

:configuration: This module requires drbd kernel module and drbd utils tool

.. code-block:: yaml

'''
from __future__ import absolute_import, print_function, unicode_literals
import logging

from salt.exceptions import CommandExecutionError
from salt.ext import six
import time

log = logging.getLogger(__name__)

__virtualname__ = 'drbd'


def __virtual__():  # pragma: no cover
    '''
    Only load if the drbd module is in __salt__
    '''
    return 'drbd.status' in __salt__


def _resource_not_exist(name):
    cmd = 'drbdadm dump {}'.format(name)
    result = __salt__['cmd.retcode'](cmd)

    return bool(result)


def _get_res_status(name):
    try:
        result = __salt__['drbd.status'](name=name)
    except CommandExecutionError as err:
        log.error(six.text_type(err))
        return None

    if not result:
        return None

    for res in result:
        if res['resource name'] == name:
            log.debug(res)
            return res

    return None


def _get_resource_list():
    ret = []
    cmd = 'drbdadm dump all'

    for line in __salt__['cmd.run'](cmd).splitlines():
        if line.startswith('resource'):
            ret.append(line.split()[1])

    return ret


def initialized(name, force=True):
    '''
    Make sure the DRBD resource is initialized.

    name
        Name of the DRBD resource.

    force
        Force to recreate the metadata.

    '''

    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': '',
    }

    # Check resource exist
    if _resource_not_exist(name):
        ret['comment'] = 'Resource {} not defined in your config.'.format(name)
        return ret

    # Check already finished
    msg = 'There appears to be a v09| is configured!'
    cmd = 'echo no|drbdadm create-md {} 2>&1 |grep -E "{}" >/dev/null'.format(
        name, msg)
    result = __salt__['cmd.retcode'](cmd, python_shell=True)

    if result == 0:
        ret['result'] = True
        ret['comment'] = 'Resource {} has already initialized.'.format(name)
        return ret

    # Do nothing for test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Resource {} would be initialized.'.format(name)
        ret['changes']['name'] = name
        return ret

    try:
        # Do real job
        result = __salt__['drbd.createmd'](
            name=name,
            force=force)

        if result:
            ret['comment'] = 'Error in initialize {}.'.format(name)
            ret['result'] = False
            return ret

        ret['changes']['name'] = name
        ret['comment'] = 'Resource {} metadata initialized.'.format(name)
        ret['result'] = True
        return ret

    except CommandExecutionError as err:
        ret['comment'] = six.text_type(err)
        return ret


def started(name):
    '''
    Make sure the DRBD resource is started.

    name
        Name of the DRBD resource.

    '''

    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': '',
    }

    # Check resource exist
    if _resource_not_exist(name):
        ret['comment'] = 'Resource {} not defined in your config.'.format(name)
        return ret

    # Check already finished
    res = _get_res_status(name)
    if res:
        ret['result'] = True
        ret['comment'] = 'Resource {} is already started.'.format(name)
        return ret

    # Do nothing for test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Resource {} would be started.'.format(name)
        ret['changes']['name'] = name
        return ret

    try:
        # Do real job
        result = __salt__['drbd.up'](name=name)

        if result:
            ret['comment'] = 'Error in start {}.'.format(name)
            ret['result'] = False
            return ret

        ret['changes']['name'] = name
        ret['comment'] = 'Resource {} is started.'.format(name)
        ret['result'] = True
        return ret

    except CommandExecutionError as err:
        ret['comment'] = six.text_type(err)
        return ret


def stopped(name):
    '''
    Make sure the DRBD resource is stopped.

    name
        Name of the DRBD resource.

    '''
    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': '',
    }

    # Check resource exist
    if _resource_not_exist(name):
        ret['comment'] = 'Resource {} not defined in your config.'.format(name)
        return ret

    # Check already finished
    res = _get_res_status(name)
    if not res:
        ret['result'] = True
        ret['comment'] = 'Resource {} is already stopped.'.format(name)
        return ret

    # Do nothing for test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Resource {} would be stopped.'.format(name)
        ret['changes']['name'] = name
        return ret

    try:
        # Do real job
        result = __salt__['drbd.down'](name=name)

        if result:
            ret['comment'] = 'Error in stop {}.'.format(name)
            ret['result'] = False
            return ret

        ret['changes']['name'] = name
        ret['comment'] = 'Resource {} is stopped.'.format(name)
        ret['result'] = True
        return ret

    except CommandExecutionError as err:
        ret['comment'] = six.text_type(err)
        return ret


def promoted(name, force=False):
    '''
    Make sure the DRBD resource is being primary.

    name
        Name of the DRBD resource.

    force
        Force to initial sync. Default: False

    '''

    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': '',
    }

    # Check resource exist
    if _resource_not_exist(name):
        ret['comment'] = 'Resource {} not defined in your config.'.format(name)
        return ret

    # Check resource is running
    res = _get_res_status(name)
    if res:
        if res['local role'] == 'Primary':
            ret['result'] = True
            ret['comment'] = 'Resource {} has already been promoted.'.format(name)
            return ret
    else:
        ret['comment'] = 'Resource {} is currently stop.'.format(name)
        return ret

    # Do nothing for test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Resource {} would be promoted.'.format(name)
        ret['changes']['name'] = name
        return ret

    try:
        # Do real job
        result = __salt__['drbd.primary'](
            name=name,
            force=force)

        if result:
            ret['comment'] = 'Error in promoting {}.'.format(name)
            ret['result'] = False
            return ret

        ret['changes']['name'] = name
        ret['comment'] = 'Resource {} is promoted.'.format(name)
        ret['result'] = True
        return ret

    except CommandExecutionError as err:
        ret['comment'] = six.text_type(err)
        return ret


def demoted(name):
    '''
    Make sure the DRBD resource is being secondary.

    name
        Name of the DRBD resource.

    '''

    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': '',
    }

    # Check resource exist
    if _resource_not_exist(name):
        ret['comment'] = 'Resource {} not defined in your config.'.format(name)
        return ret

    # Check resource is running
    res = _get_res_status(name)
    if res:
        if res['local role'] == 'Secondary':
            ret['result'] = True
            ret['comment'] = 'Resource {} has already been demoted.'.format(name)
            return ret
    else:
        ret['comment'] = 'Resource {} is currently stop.'.format(name)
        return ret

    # Do nothing for test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Resource {} would be demoted.'.format(name)
        ret['changes']['name'] = name
        return ret

    try:
        # Do real job
        result = __salt__['drbd.secondary'](name=name)

        if result:
            ret['comment'] = 'Error in demoting {}.'.format(name)
            ret['result'] = False
            return ret

        ret['changes']['name'] = name
        ret['comment'] = 'Resource {} is demoted.'.format(name)
        ret['result'] = True
        return ret

    except CommandExecutionError as err:
        ret['comment'] = six.text_type(err)
        return ret


def wait_for_successful_synced(name, interval=30, timeout=600, **kwargs):
    '''
    Query a drbd resource until fully synced for all volumes.
    If not synced, will fail after timeout.

    name:
        Resource name. Not support all.

    interval:
        Interval to check the sync status. Default: 30

    timeout:
        Timeout to wait progress. Default: 600

    .. note::

        All other arguements are passed to the module drbd.check_sync_status.
    '''
    ret = {
        'name': name,
        'result': False,
        'changes': {},
        'comment': '',
    }

    # Check resource exist
    if _resource_not_exist(name):
        ret['comment'] = 'Resource {} not defined in your config.'.format(name)
        return ret

    # Check resource is running
    res = _get_res_status(name)
    if res:
        if __salt__['drbd.check_sync_status'](
                name=name,
                **kwargs):
            ret['result'] = True
            ret['comment'] = 'Resource {} has already been synced.'.format(name)
            return ret
    else:
        ret['comment'] = 'Resource {} is currently stop.'.format(name)
        return ret

    # Do nothing for test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Check {} whether be synced within {}.'.format(name, timeout)
        ret['changes']['name'] = name
        return ret

    try:
        # Do real job
        starttime = time.time()

        while True:

            if time.time() > starttime + timeout:
                ret['comment'] = 'Resource {} is not synced within {}s.'.format(
                    name, timeout)
                break

            time.sleep(interval)

            result = __salt__['drbd.check_sync_status'](
                name=name,
                **kwargs)

            if result:
                ret['changes']['name'] = name
                ret['comment'] = 'Resource {} is synced.'.format(name)
                ret['result'] = True
                return ret

        return ret

    except CommandExecutionError as err:
        ret['comment'] = six.text_type(err)
        return ret
