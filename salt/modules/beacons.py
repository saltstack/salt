# -*- coding: utf-8 -*-
'''
Module for managing the Salt beacons on a minion

.. versionadded:: 2015.8.0

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import difflib
import logging
import os

# Import Salt libs
import salt.ext.six as six
import salt.utils.event
import salt.utils.files
import salt.utils.yaml
from salt.ext.six.moves import map

# Get logging started
log = logging.getLogger(__name__)

default_event_wait = 60
__func_alias__ = {
    'list_': 'list',
    'reload_': 'reload'
}


def list_(return_yaml=True,
          include_pillar=True,
          include_opts=True,
          **kwargs):
    '''
    List the beacons currently configured on the minion

    :param return_yaml:    Whether to return YAML formatted output,
                           default ``True``

    :param include_pillar: Whether to include beacons that are
                           configured in pillar, default is ``True``.

    :param include_opts:   Whether to include beacons that are
                           configured in opts, default is ``True``.

    :return:               List of currently configured Beacons.

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.list

    '''
    beacons = None

    try:
        with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
            res = __salt__['event.fire']({'func': 'list',
                                          'include_pillar': include_pillar,
                                          'include_opts': include_opts},
                                         'manage_beacons')
            if res:
                event_ret = event_bus.get_event(
                    tag='/salt/minion/minion_beacons_list_complete',
                    wait=kwargs.get('timeout', default_event_wait))
                log.debug('event_ret %s', event_ret)
                if event_ret and event_ret['complete']:
                    beacons = event_ret['beacons']
    except KeyError:
        # Effectively a no-op, since we can't really return without an event system
        ret = {}
        ret['result'] = False
        ret['comment'] = 'Event module not available. Beacon add failed.'
        return ret

    if beacons:
        if return_yaml:
            tmp = {'beacons': beacons}
            return salt.utils.yaml.safe_dump(tmp, default_flow_style=False)
        else:
            return beacons
    else:
        return {'beacons': {}}


def list_available(return_yaml=True, **kwargs):
    '''
    List the beacons currently available on the minion

    :param return_yaml:     Whether to return YAML formatted output, default
                            ``True``
    :return:                List of currently configured Beacons.

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.list_available

    '''
    beacons = None

    try:
        with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
            res = __salt__['event.fire']({'func': 'list_available'}, 'manage_beacons')
            if res:
                event_ret = event_bus.get_event(
                    tag='/salt/minion/minion_beacons_list_available_complete',
                    wait=kwargs.get('timeout', default_event_wait))
                if event_ret and event_ret['complete']:
                    beacons = event_ret['beacons']
    except KeyError:
        # Effectively a no-op, since we can't really return without an event system
        ret = {}
        ret['result'] = False
        ret['comment'] = 'Event module not available. Beacon add failed.'
        return ret

    if beacons:
        if return_yaml:
            tmp = {'beacons': beacons}
            return salt.utils.yaml.safe_dump(tmp, default_flow_style=False)
        else:
            return beacons
    else:
        return {'beacons': {}}


def add(name, beacon_data, **kwargs):
    '''
    Add a beacon on the minion

    :param name:            Name of the beacon to configure
    :param beacon_data:     Dictionary or list containing configuration for beacon.
    :return:                Boolean and status message on success or failure of add.

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.add ps "[{'processes': {'salt-master': 'stopped', 'apache2': 'stopped'}}]"

    '''
    ret = {'comment': 'Failed to add beacon {0}.'.format(name),
           'result': False}

    if name in list_(return_yaml=False, **kwargs):
        ret['comment'] = 'Beacon {0} is already configured.'.format(name)
        return ret

    if name not in list_available(return_yaml=False, **kwargs):
        ret['comment'] = 'Beacon "{0}" is not available.'.format(name)
        return ret

    if 'test' in kwargs and kwargs['test']:
        ret['result'] = True
        ret['comment'] = 'Beacon: {0} would be added.'.format(name)
    else:
        try:
            # Attempt to load the beacon module so we have access to the validate function
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'name': name,
                                              'beacon_data': beacon_data,
                                              'func': 'validate_beacon'},
                                             'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                       tag='/salt/minion/minion_beacon_validation_complete',
                       wait=kwargs.get('timeout', default_event_wait))
                    valid = event_ret['valid']
                    vcomment = event_ret['vcomment']

                if not valid:
                    ret['result'] = False
                    ret['comment'] = ('Beacon {0} configuration invalid, '
                                      'not adding.\n{1}'.format(name, vcomment))
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon add failed.'

        try:
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'name': name,
                                              'beacon_data': beacon_data,
                                              'func': 'add'}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacon_add_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    if event_ret and event_ret['complete']:
                        beacons = event_ret['beacons']
                        if name in beacons and beacons[name] == beacon_data:
                            ret['result'] = True
                            ret['comment'] = 'Added beacon: {0}.'.format(name)
                    elif event_ret:
                        ret['result'] = False
                        ret['comment'] = event_ret['comment']
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Did not receive the beacon add complete event before the timeout of {}s'.format(
                            kwargs.get('timeout', default_event_wait)
                        )
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon add failed.'
    return ret


def modify(name, beacon_data, **kwargs):
    '''
    Modify an existing beacon

    :param name:            Name of the beacon to configure
    :param beacon_data:     Dictionary or list containing updated configuration for beacon.
    :return:                Boolean and status message on success or failure of modify.

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.modify ps "[{'salt-master': 'stopped'}, {'apache2': 'stopped'}]"
    '''

    ret = {'comment': '',
           'result': True}

    current_beacons = list_(return_yaml=False, **kwargs)
    if name not in current_beacons:
        ret['comment'] = 'Beacon {0} is not configured.'.format(name)
        return ret

    if 'test' in kwargs and kwargs['test']:
        ret['result'] = True
        ret['comment'] = 'Beacon: {0} would be added.'.format(name)
    else:
        try:
            # Attempt to load the beacon module so we have access to the validate function
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'name': name,
                                              'beacon_data': beacon_data,
                                              'func': 'validate_beacon'},
                                             'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacon_validation_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    valid = event_ret['valid']
                    vcomment = event_ret['vcomment']

                if not valid:
                    ret['result'] = False
                    ret['comment'] = ('Beacon {0} configuration invalid, '
                                      'not adding.\n{1}'.format(name, vcomment))
                    return ret

        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon modify failed.'

        if not valid:
            ret['result'] = False
            ret['comment'] = ('Beacon {0} configuration invalid, '
                              'not modifying.\n{1}'.format(name, vcomment))
            return ret

        _current = current_beacons[name]
        _new = beacon_data

        if _new == _current:
            ret['comment'] = 'Job {0} in correct state'.format(name)
            return ret

        _current_lines = []
        for _item in _current:
            _current_lines.extend(['{0}:{1}\n'.format(key, value)
                                  for (key, value) in six.iteritems(_item)])
        _new_lines = []
        for _item in _new:
            _new_lines.extend(['{0}:{1}\n'.format(key, value)
                              for (key, value) in six.iteritems(_item)])
        _diff = difflib.unified_diff(_current_lines, _new_lines)

        ret['changes'] = {}
        ret['changes']['diff'] = ''.join(_diff)

        try:
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'name': name, 'beacon_data': beacon_data, 'func': 'modify'}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacon_modify_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    if event_ret and event_ret['complete']:
                        beacons = event_ret['beacons']
                        if name in beacons and beacons[name] == beacon_data:
                            ret['result'] = True
                            ret['comment'] = 'Modified beacon: {0}.'.format(name)
                    elif event_ret:
                        ret['result'] = False
                        ret['comment'] = event_ret['comment']
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Did not receive the beacon modify complete  event before the timeout of {}s'.format(
                            kwargs.get('timeout', default_event_wait)
                        )
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon add failed.'
    return ret


def delete(name, **kwargs):
    '''
    Delete a beacon item

    :param name:            Name of the beacon to delete
    :return:                Boolean and status message on success or failure of delete.

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
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'name': name, 'func': 'delete'}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacon_delete_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    if event_ret and event_ret['complete']:
                        beacons = event_ret['beacons']
                        if name not in beacons:
                            ret['result'] = True
                            ret['comment'] = 'Deleted beacon: {0}.'.format(name)
                            return ret
                    elif event_ret:
                        ret['result'] = False
                        ret['comment'] = event_ret['comment']
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Did not receive the beacon delete complete event before the timeout of {}s'.format(
                            kwargs.get('timeout', default_event_wait)
                        )
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon add failed.'
    return ret


def save(**kwargs):
    '''
    Save all beacons on the minion

    :return:                Boolean and status message on success or failure of save.

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.save
    '''

    ret = {'comment': [],
           'result': True}

    beacons = list_(return_yaml=False, include_pillar=False, **kwargs)

    # move this file into an configurable opt
    sfn = os.path.join(os.path.dirname(__opts__['conf_file']),
                       os.path.dirname(__opts__['default_include']),
                       'beacons.conf')
    if beacons:
        tmp = {'beacons': beacons}
        yaml_out = salt.utils.yaml.safe_dump(tmp, default_flow_style=False)
    else:
        yaml_out = ''

    try:
        with salt.utils.files.fopen(sfn, 'w+') as fp_:
            fp_.write(yaml_out)
        ret['comment'] = 'Beacons saved to {0}.'.format(sfn)
    except (IOError, OSError):
        ret['comment'] = 'Unable to write to beacons file at {0}. Check ' \
                         'permissions.'.format(sfn)
        ret['result'] = False
    return ret


def enable(**kwargs):
    '''
    Enable all beacons on the minion

    Returns:
        bool: Boolean and status message on success or failure of enable.

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
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'func': 'enable'}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacons_enabled_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    if event_ret and event_ret['complete']:
                        beacons = event_ret['beacons']
                        if 'enabled' in beacons and beacons['enabled']:
                            ret['result'] = True
                            ret['comment'] = 'Enabled beacons on minion.'
                        elif event_ret:
                            ret['result'] = False
                            ret['comment'] = 'Failed to enable beacons on minion.'
                        else:
                            ret['result'] = False
                            ret['comment'] = 'Did not receive the beacon enabled complete event before the timeout of {}s'.format(
                                kwargs.get('timeout', default_event_wait)
                            )
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacons enable job failed.'
    return ret


def disable(**kwargs):
    '''
    Disable all beacons jobs on the minion

    :return:                Boolean and status message on success or failure of disable.

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
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'func': 'disable'}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacons_disabled_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    log.debug('event_ret %s', event_ret)
                    if event_ret and event_ret['complete']:
                        beacons = event_ret['beacons']
                        if 'enabled' in beacons and not beacons['enabled']:
                            ret['result'] = True
                            ret['comment'] = 'Disabled beacons on minion.'
                        elif event_ret:
                            ret['result'] = False
                            ret['comment'] = 'Failed to disable beacons on minion.'
                        else:
                            ret['result'] = False
                            ret['comment'] = 'Did not receive the beacon disabled complete event before the timeout of {}s'.format(
                                kwargs.get('timeout', default_event_wait)
                            )
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacons enable job failed.'
    return ret


def _get_beacon_config_dict(beacon_config):
    beacon_config_dict = {}
    if isinstance(beacon_config, list):
        list(map(beacon_config_dict.update, beacon_config))
    else:
        beacon_config_dict = beacon_config

    return beacon_config_dict


def enable_beacon(name, **kwargs):
    '''
    Enable beacon on the minion

    :name:                  Name of the beacon to enable.
    :return:                Boolean and status message on success or failure of enable.

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.enable_beacon ps
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Beacon name is required.'
        ret['result'] = False
        return ret

    if 'test' in kwargs and kwargs['test']:
        ret['comment'] = 'Beacon {0} would be enabled.'.format(name)
    else:
        _beacons = list_(return_yaml=False, **kwargs)
        if name not in _beacons:
            ret['comment'] = 'Beacon {0} is not currently configured.'.format(name)
            ret['result'] = False
            return ret

        try:
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'func': 'enable_beacon', 'name': name}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacon_enabled_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    if event_ret and event_ret['complete']:
                        beacons = event_ret['beacons']
                        beacon_config_dict = _get_beacon_config_dict(beacons[name])

                        if 'enabled' in beacon_config_dict and beacon_config_dict['enabled']:
                            ret['result'] = True
                            ret['comment'] = 'Enabled beacon {0} on minion.'.format(name)
                        else:
                            ret['result'] = False
                            ret['comment'] = 'Failed to enable beacon {0} on minion.'.format(name)
                    elif event_ret:
                        ret['result'] = False
                        ret['comment'] = event_ret['comment']
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Did not receive the beacon enabled complete event before the timeout of {}s'.format(
                            kwargs.get('timeout', default_event_wait)
                        )
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon enable job failed.'
    return ret


def disable_beacon(name, **kwargs):
    '''
    Disable beacon on the minion

    :name:                  Name of the beacon to disable.
    :return:                Boolean and status message on success or failure of disable.

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.disable_beacon ps
    '''

    ret = {'comment': [],
           'result': True}

    if not name:
        ret['comment'] = 'Beacon name is required.'
        ret['result'] = False
        return ret

    if 'test' in kwargs and kwargs['test']:
        ret['comment'] = 'Beacons would be enabled.'
    else:
        _beacons = list_(return_yaml=False, **kwargs)
        if name not in _beacons:
            ret['comment'] = 'Beacon {0} is not currently configured.'.format(name)
            ret['result'] = False
            return ret

        try:
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'func': 'disable_beacon', 'name': name}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacon_disabled_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    if event_ret and event_ret['complete']:
                        beacons = event_ret['beacons']
                        beacon_config_dict = _get_beacon_config_dict(beacons[name])

                        if 'enabled' in beacon_config_dict and not beacon_config_dict['enabled']:
                            ret['result'] = True
                            ret['comment'] = 'Disabled beacon {0} on minion.'.format(name)
                        else:
                            ret['result'] = False
                            ret['comment'] = 'Failed to disable beacon on minion.'
                    elif event_ret:
                        ret['result'] = False
                        ret['comment'] = event_ret['comment']
                    else:
                        ret['result'] = False
                        ret['comment'] = 'Did not receive the beacon disabled complete event before the timeout of {}s'.format(
                            kwargs.get('timeout', default_event_wait)
                        )
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon disable job failed.'
    return ret


def reset(**kwargs):
    '''
    Resest beacon configuration on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' beacons.reset
    '''

    ret = {'comment': [],
           'result': True}

    if kwargs.get('test'):
        ret['comment'] = 'Beacons would be reset.'
    else:
        try:
            with salt.utils.event.get_event('minion', opts=__opts__, listen=True) as event_bus:
                res = __salt__['event.fire']({'func': 'reset'}, 'manage_beacons')
                if res:
                    event_ret = event_bus.get_event(
                        tag='/salt/minion/minion_beacon_reset_complete',
                        wait=kwargs.get('timeout', default_event_wait))
                    if event_ret and event_ret['complete']:
                        ret['result'] = True
                        ret['comment'] = 'Beacon configuration reset.'
                    else:
                        ret['result'] = False
                        if ret is not None:
                            ret['comment'] = event_ret['comment']
                        else:
                            ret['comment'] = 'Beacon reset event never received'
                    return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret['comment'] = 'Event module not available. Beacon disable job failed.'
    return ret
