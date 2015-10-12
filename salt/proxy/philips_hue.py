# -*- coding: utf-8 -*-
'''
Philips HUE lamps module for proxy.
'''

from __future__ import absolute_import

# Import python libs
import logging

__proxyenabled__ = ['philips_hue']

GRAINS_CACHE = {}
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


def init(opts):
    '''
    Initialize the module.
    '''


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


def _set(lamp_id, state):
    '''
    Set state to the device by ID.

    :param lamp_id:
    :param state:
    :return:
    '''
    res = json.loads(requests.put(CONFIG['url']+"/lights/"
                                   + str(lamp_id) + "/state", json=state).content)
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

    return [int(dev) for dev in params['id'].split(",")]


# Callers
def call_lights(*args, **kwargs):
    '''
    Get info about available lamps.
    '''
    return json.loads(requests.get(CONFIG['url'] + "/lights").content)


def call_ping(*args, **kwargs):
    '''
    Ping the lamps
    '''
    ping(*args, **kw)


def call_status(*args, **kwargs):
    '''
    Return lamps status.
    '''
    return {
        1: True,
        2: True,
        3: False,
        }


def call_alert(*args, **kw):
    '''
    Blink the alert.
    '''
    return {
        1: 'Alerted',
        2: 'Alerted',
        3: 'Skipped',
    }
