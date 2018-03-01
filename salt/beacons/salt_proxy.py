# -*- coding: utf-8 -*-
'''
    Beacon to manage and report the status of
    one or more salt proxy processes

    .. versionadded:: 2015.8.3
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import logging
from salt.ext.six.moves import map

log = logging.getLogger(__name__)


def _run_proxy_processes(proxies):
    '''
    Iterate over a list of proxy
    names and restart any that
    aren't running
    '''
    ret = []
    for proxy in proxies:
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


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for adb beacon should be a dictionary with states array
    if not isinstance(config, list):
        log.info('Configuration for salt_proxy beacon must be a list.')
        return False, ('Configuration for salt_proxy beacon must be a list.')

    else:
        _config = {}
        list(map(_config.update, config))

        if 'proxies' not in _config:
            return False, ('Configuration for salt_proxy'
                           ' beacon requires proxies.')
        else:
            if not isinstance(_config['proxies'], dict):
                return False, ('Proxies for salt_proxy '
                               'beacon must be a dictionary.')


def beacon(config):
    '''
    Handle configured proxies

    .. code-block:: yaml

        beacons:
          salt_proxy:
            - proxies:
                p8000: {}
                p8001: {}
    '''
    log.trace('salt proxy beacon called')

    _config = {}
    list(map(_config.update, config))

    return _run_proxy_processes(_config['proxies'])
