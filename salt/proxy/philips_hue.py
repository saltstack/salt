# -*- coding: utf-8 -*-
#
# Copyright 2015 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
Philips HUE lamps module for proxy.
'''

from __future__ import absolute_import

# Import python libs
import logging
import requests
import time
import json
from salt.exceptions import (CommandExecutionError, MinionError)


__proxyenabled__ = ['philips_hue']

GRAINS_CACHE = {}
CONFIG = {}
log = logging.getLogger(__file__)


class Const:
    '''
    Constants for the lamp operations.
    '''
    LAMP_ON = {"on": True, "transitiontime": 0}
    LAMP_OFF = {"on": False, "transitiontime": 0}


def __virtual__():
    '''
    Validate the module.
    '''
    return True


def init(cnf):
    '''
    Initialize the module.
    '''
    host = cnf.get('proxy', {}).get('host')
    if not host:
        raise MinionError(message="Cannot find 'host' parameter in the proxy configuration")

    user = cnf.get('proxy', {}).get('user')
    if not user:
        raise MinionError(message="Cannot find 'user' parameter in the proxy configuration")

    CONFIG['url'] = "http://{0}/api/{1}".format(host, user)


def grains():
    '''
    Get the grains from the proxied device
    '''
    return grains_refresh()


def grains_refresh():
    '''
    Refresh the grains from the proxied device
    '''
    if not GRAINS_CACHE:
        GRAINS_CACHE['vendor'] = 'Philips'
        GRAINS_CACHE['product'] = 'Hue Lamps'
        
    return GRAINS_CACHE


def ping(*args, **kw):
    '''
    Ping the lamps.
    '''
    # Here blink them
    return True


def shutdown(opts, *args, **kw):
    '''
    Shuts down the service.
    '''
    # This is no-op method, which is required but makes nothing at this point.
    return True


def _set(lamp_id, state, method="state"):
    '''
    Set state to the device by ID.

    :param lamp_id:
    :param state:
    :return:
    '''
    url = "{0}/lights/{1}".format(CONFIG['url'], lamp_id) + (method and "/{0}".format(method) or '')
    res = json.loads(requests.put(url, json=state).content)
    res = len(res) > 1 and res[-1] or res[0]
    if res.get('success'):
        res = {'result': True}
    elif res.get('error'):
        res = {'result': False,
               'description': res['error']['description'],
               'type': res['error']['type']}

    return res


def _get_devices(params):
    '''
    Parse device(s) ID(s) from the common params.

    :param params:
    :return:
    '''
    if 'id' not in params:
        raise CommandExecutionError("Parameter ID is required.")

    return type(params['id']) == int and [params['id']] \
           or [int(dev) for dev in params['id'].split(",")]


def _get_lights():
    '''
    Get all available lighting devices.

    :return:
    '''
    return json.loads(requests.get(CONFIG['url'] + "/lights").content)


# Callers
def call_lights(*args, **kwargs):
    '''
    Get info about available lamps.
    '''
    res = dict()
    lights = _get_lights()
    if 'id' in kwargs:
        for dev_id in _get_devices(kwargs):
            if lights.get(str(dev_id)):
                res[dev_id] = lights[str(dev_id)]

    return res or False


def call_switch(*args, **kwargs):
    '''
    Switch lamp ON/OFF.

    If no particular state is passed,
    then lamp will be switched to the opposite state.

    Options:

    * **id**: Specifies a device ID. Can be a comma-separated values. All, if omitted.
    * **on**: True or False. Inverted current, if omitted

    CLI Example:

    .. code-block:: bash

        salt '*' hue.switch
        salt '*' hue.switch id=1
        salt '*' hue.switch id=1,2,3 on=True
    '''
    out = dict()
    devices = _get_lights()
    for dev_id in ('id' not in kwargs and sorted(devices.keys()) or _get_devices(kwargs)):
        if 'on' in kwargs:
            state = kwargs['on'] and Const.LAMP_ON or Const.LAMP_OFF
        else:
            # Invert the current state
            state = devices[str(dev_id)]['state']['on'] and Const.LAMP_OFF or Const.LAMP_ON
        out[dev_id] = _set(dev_id, state)

    return out


def call_blink(*args, **kwargs):
    '''
    Blink a lamp. If lamp is ON, then blink ON-OFF-ON, otherwise OFF-ON-OFF.

    Options:

    * **id**: Specifies a device ID. Can be a comma-separated values. All, if omitted.
    * **pause**: Time in seconds. Can be less than 1, i.e. 0.7, 0.5 sec.

    CLE Example:

    .. code-block:: bash

        salt '*' hue.blink id=1
        salt '*' hue.blink id=1,2,3
    '''
    devices = _get_lights()
    pause = kwargs.get('pause', 0)
    res = dict()
    for dev_id in ('id' not in kwargs and sorted(devices.keys()) or _get_devices(kwargs)):
        state = devices[str(dev_id)]['state']['on']
        _set(dev_id, state and Const.LAMP_OFF or Const.LAMP_ON)
        if pause:
            time.sleep(pause)
        res[dev_id] = _set(dev_id, not state and Const.LAMP_OFF or Const.LAMP_ON)

    return res


def call_ping(*args, **kwargs):
    '''
    Ping the lamps
    '''
    errors = dict()
    for dev_id, dev_status in call_blink().items():
        if not dev_status['result']:
            errors[dev_id] = False

    return errors or True


def call_status(*args, **kwargs):
    '''
    Return the status of the lamps.
    '''
    res = dict()
    devices = _get_devices()
    for dev_id in devices:
        res[dev_id] = {
            'on': devices[dev_id]['state']['on'],
            'reachable': devices[dev_id]['state']['reachable']
        }

    return res


def call_rename(*args, **kwargs):
    '''
    Rename a device.

    Options:

    * **id**: Specifies a device ID. Only one device at a time.
    * **title**: Title of the device.

    CLE Example:

    .. code-block:: bash

        salt '*' hue.rename id=1 title='WC for cats'
    '''
    dev_id = _get_devices(kwargs)
    if len(dev_id) > 1:
        raise CommandExecutionError("Only one device can be renamed at a time")

    if 'title' not in kwargs:
        raise CommandExecutionError("Title is missing")

    return _set(dev_id[0], {"name": kwargs['title']}, method="")


def call_alert(*args, **kwargs):
    '''
    Lamp alert

    Options:

    * **id**: Specifies a device ID. Can be comma-separated ids or all, if omitted.
    * **on**: Turns on or off an alert. Default is True.

    CLE Example:

    .. code-block:: bash

        salt '*' hue.alert
        salt '*' hue.alert id=1
        salt '*' hue.alert id=1,2,3 on=false
    '''
    res = dict()

    devices = _get_lights()
    for dev_id in ('id' not in kwargs and sorted(devices.keys()) or _get_devices(kwargs)):
        res[dev_id] = _set(dev_id, {"alert": kwargs.get("on", True) and "lselect" or "none"})

    return res


def call_effect(*args, **kwargs):
    '''
    Set an effect to the lamp.

    Options:

    * **id**: Specifies a device ID. Can be comma-separated ids or all, if omitted.
    * **type**: Type of the effect. Possible values are "none" or "colorloop". Default "none".

    CLE Example:

    .. code-block:: bash

        salt '*' hue.alert
        salt '*' hue.alert id=1
        salt '*' hue.alert id=1,2,3 on=false
    '''
    res = dict()

    devices = _get_lights()
    for dev_id in ('id' not in kwargs and sorted(devices.keys()) or _get_devices(kwargs)):
        res[dev_id] = _set(dev_id, {"effect": kwargs.get("type", "none")})

    return res
