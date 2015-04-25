# -*- coding: utf-8 -*-
'''
Module for managing the Salt schedule on a minion

.. versionadded:: Beryllium

'''

# Import Python libs
from __future__ import absolute_import
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
    List the jobs currently scheduled on the minion

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
