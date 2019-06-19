# -*- coding: utf-8 -*-
'''
Beacon to emit when a display is available to a linux machine

.. versionadded:: 2016.3.0
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import logging

# Salt libs
import salt.utils.path
from salt.ext.six.moves import map

log = logging.getLogger(__name__)

__virtualname__ = 'glxinfo'

last_state = {}


def __virtual__():

    which_result = salt.utils.path.which('glxinfo')
    if which_result is None:
        return False
    else:
        return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for glxinfo beacon should be a dictionary
    if not isinstance(config, list):
        return False, ('Configuration for glxinfo beacon must be a list.')

    _config = {}
    list(map(_config.update, config))

    if 'user' not in _config:
        return False, ('Configuration for glxinfo beacon must '
                       'include a user as glxinfo is not available to root.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Emit the status of a connected display to the minion

    Mainly this is used to detect when the display fails to connect
    for whatever reason.

    .. code-block:: yaml

        beacons:
          glxinfo:
            - user: frank
            - screen_event: True

    '''

    log.trace('glxinfo beacon starting')
    ret = []

    _config = {}
    list(map(_config.update, config))

    retcode = __salt__['cmd.retcode']('DISPLAY=:0 glxinfo',
                                      runas=_config['user'], python_shell=True)

    if 'screen_event' in _config and _config['screen_event']:
        last_value = last_state.get('screen_available', False)
        screen_available = retcode == 0
        if last_value != screen_available or 'screen_available' not in last_state:
            ret.append({'tag': 'screen_event', 'screen_available': screen_available})

        last_state['screen_available'] = screen_available

    return ret
