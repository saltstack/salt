# -*- coding: utf-8 -*-
'''
Module for managing the Salt beacons on a minion

.. versionadded:: Beryllium

'''

# Import Python libs
from __future__ import absolute_import
import os
import yaml

import salt.utils

import logging
log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list',
    'reload_': 'reload'
}


def list_(return_yaml=True):
    '''
    List the beacons currently configured on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.list

    '''

    if 'beacons' in __opts__:
        beacons = __opts__['beacons'].copy()
    else:
        return {'beacons': {}}

    if beacons:
        if return_yaml:
            tmp = {'beacons': beacons}
            yaml_out = yaml.safe_dump(tmp, default_flow_style=False)
            return yaml_out
        else:
            return beacons
    else:
        return {'beacons': {}}


def add(name, beacon_data, **kwargs):
    '''
    Add a beacon on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.add

    '''
    ret = {'comment': 'Failed to add beacon {0}.'.format(name),
           'result': False}

    if 'test' in kwargs and kwargs['test']:
        ret['result'] = True
        ret['comment'] = 'Beacon: {0} would be added.'.format(name)
    else:
        # Attempt to load the beacon module so we have access to the validate function
        try:
            beacon_module = __import__('salt.beacons.' + name, fromlist=['validate'])
            log.debug('Successfully imported beacon.')
        except ImportError:
            ret['comment'] = 'Beacon {0} does not exist'.format(name)
            return ret

        # Attempt to validate
        if hasattr(beacon_module, 'validate'):
            valid = beacon_module.validate(beacon_data)
        else:
            log.info('Beacon {0} does not have a validate'
                     ' function,  skipping validation.'.format(name))
            valid = True

        if not valid:
            ret['comment'] = 'Beacon {0} configuration invalid, not adding.'.format(name)
            return ret

        try:
            eventer = salt.utils.event.get_event('minion', opts=__opts__)
            res = __salt__['event.fire']({'name': name, 'beacon_data': beacon_data, 'func': 'add'}, 'manage_beacons')
            if res:
                event_ret = eventer.get_event(tag='/salt/minion/minion_beacon_add_complete', wait=30)
                if event_ret and event_ret['complete']:
                    beacons = event_ret['beacons']
                    if name in beacons and beacons[name] == beacon_data:
                        ret['result'] = True
                        ret['comment'] = 'Added beacon: {0}.'.format(name)
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon add failed.'
    return ret


def delete(name, **kwargs):
    '''
    Delete a beacon item

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.delete ps

        salt '*' beacons.delete load

    '''

    ret = {'comment': 'Failed to delete beacon {0}.'.format(name),
           'result': False}

    if 'test' in kwargs and kwargs['test']:
        ret['result'] = True
        ret['comment'] = 'Beacon: {0} would be deleted.'.format(name)
    else:
        try:
            eventer = salt.utils.event.get_event('minion', opts=__opts__)
            res = __salt__['event.fire']({'name': name, 'func': 'delete'}, 'manage_beacons')
            if res:
                event_ret = eventer.get_event(tag='/salt/minion/minion_beacon_delete_complete', wait=30)
                if event_ret and event_ret['complete']:
                    beacons = event_ret['beacons']
                    if name not in beacons:
                        ret['result'] = True
                        ret['comment'] = 'Deleted beacon: {0}.'.format(name)
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon add failed.'
    return ret


def save():
    '''
    Save all beacons on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.save
    '''

    ret = {'comment': [],
           'result': True}

    beacons = list_(return_yaml=False)

    # move this file into an configurable opt
    sfn = '{0}/{1}/beacons.conf'.format(__opts__['config_dir'],
                                        os.path.dirname(__opts__['default_include']))
    if beacons:
        tmp = {'beacons': beacons}
        yaml_out = yaml.safe_dump(tmp, default_flow_style=False)
    else:
        yaml_out = ''

    try:
        with salt.utils.fopen(sfn, 'w+') as fp_:
            fp_.write(yaml_out)
        ret['comment'] = 'Beacons saved to {0}.'.format(sfn)
    except (IOError, OSError):
        ret['comment'] = 'Unable to write to beacons file at {0}. Check permissions.'.format(sfn)
        ret['result'] = False
    return ret


def enable(**kwargs):
    '''
    Enable all beacons on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.enable
    '''

    ret = {'comment': [],
           'result': True}

    if 'test' in kwargs and kwargs['test']:
        ret['comment'] = 'Beacons would be enabled.'
    else:
        try:
            eventer = salt.utils.event.get_event('minion', opts=__opts__)
            res = __salt__['event.fire']({'func': 'enable'}, 'manage_beacons')
            if res:
                event_ret = eventer.get_event(tag='/salt/minion/minion_beacons_enabled_complete', wait=30)
                if event_ret and event_ret['complete']:
                    beacons = event_ret['beacons']
                    if 'enabled' in beacons and beacons['enabled']:
                        ret['result'] = True
                        ret['comment'] = 'Enabled beacons on minion.'
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Failed to enable beacons on minion.'
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacons enable job failed.'
    return ret


def disable(**kwargs):
    '''
    Disable all beaconsd jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.disable
    '''

    ret = {'comment': [],
           'result': True}

    if 'test' in kwargs and kwargs['test']:
        ret['comment'] = 'Beacons would be disabled.'
    else:
        try:
            eventer = salt.utils.event.get_event('minion', opts=__opts__)
            res = __salt__['event.fire']({'func': 'disable'}, 'manage_beacons')
            if res:
                event_ret = eventer.get_event(tag='/salt/minion/minion_beacons_disabled_complete', wait=30)
                log.debug('event_ret {0}'.format(event_ret))
                if event_ret and event_ret['complete']:
                    beacons = event_ret['beacons']
                    if 'enabled' in beacons and not beacons['enabled']:
                        ret['result'] = True
                        ret['comment'] = 'Disabled beacons on minion.'
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Failed to disable beacons on minion.'
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacons enable job failed.'
    return ret

