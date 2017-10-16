# -*- coding: utf-8 -*-
'''
    Beacon to manage and report the status of
    one or more salt proxy processes

    .. versionadded:: 2015.8.3
'''

# Import python libs
from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)


def _run_proxy_processes(proxies):
    '''
    Iterate over a list of proxy
    names and restart any that
    aren't running
    '''
    ret = []
    for prox_ in proxies:
        # prox_ is a dict
        proxy = prox_.keys()[0]
        result = {}
        if not __salt__['salt_proxy.is_running'](proxy)['result']:
            __salt__['salt_proxy.configure_proxy'](proxy, start=True)
            result[proxy] = 'Proxy {0} was started'.format(proxy)
        else:
            msg = 'Proxy {0} is already running'.format(proxy)
            result[proxy] = msg
            log.debug(msg)
        ret.append(result)
    return ret


def beacon(proxies):
    '''
    Handle configured proxies

    .. code-block:: yaml

        beacons:
          salt_proxy:
            - p8000: {}
            - p8001: {}
    '''
    log.trace('salt proxy beacon called')

    return _run_proxy_processes(proxies)
