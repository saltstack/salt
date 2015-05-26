# -*- coding: utf-8 -*-
'''
Send events covering service status
'''

import os
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

last_status = {}


def beacon(config):
    '''
    Scan for the configured services and fire events

    Example Config

    .. code-block:: yaml

        beacons:
          service:
            salt-master:
            mysql:

    The config above sets up beacons to check for
    the salt-master and mysql services.

    The config also supports two other parameters for each service:

    `onchangeonly`: when `onchangeonly` is True the beacon will fire
    events only when the service status changes.  Otherwise, it will fire an event
    at each beacon interval.  The default is False.

    `uncleanshutdown`: If `uncleanshutdown` is present it should point to the location
    of a pid file for the service.  Most services will not clean up this pid file
    if they are shutdown uncleanly (e.g. via `kill -9`) or if they are terminated
    through a crash such as a segmentation fault.  If the file is present, then
    the beacon will add `uncleanshutdown: True` to the event.  If not present,
    the field will be False.  The field is only added when the service is NOT running.
    Omitting the configuration variable altogether will turn this feature off.

    Here is an example that will fire an event whenever the state of nginx changes
    and report an uncleanshutdown.  This example is for Arch, which places nginx's
    pid file in `/run`.

    .. code-block:: yaml

        beacons:
          service:
            nginx:
              onchangeonly: True
              uncleanshutdown: /run/nginx.pid
    '''
    ret = []
    for service in config:
        ret_dict = {}
        ret_dict[service] = {'running': __salt__['service.status'](service)}

        # We only want to report the nature of the shutdown
        # if the current running status is False
        # as well as if the config for the beacon asks for it
        if 'uncleanshutdown' in config[service] and not ret_dict[service]['running']:
            filename = config[service]['uncleanshutdown']
            if os.path.exists(filename):
                ret_dict[service]['shutdown'] = 'unclean'
            else:
                ret_dict[service]['shutdown'] = 'clean'

        if 'onchangeonly' in config[service] and config[service]['onchangeonly'] is True:
            if service not in last_status:
                last_status[service] = ''
            if last_status[service] != ret_dict[service]:
                last_status[service] = ret_dict[service]
                ret.append(ret_dict)
        else:
            ret.append(ret_dict)

    return ret
