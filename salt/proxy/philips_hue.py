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


# Callers
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


def call_alert(*args, **kwargs):
    '''
    Blink the alert.
    '''
    return {
        1: 'Alerted',
        2: 'Alerted',
        3: 'Skipped',
    }
