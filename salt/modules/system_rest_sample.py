# -*- coding: utf-8 -*-
'''
Provide the service module for the proxy-minion REST sample
'''
# Import python libs
from __future__ import absolute_import
import logging

__proxyenabled__ = ['rest_sample']

log = logging.getLogger(__name__)

__func_alias__ = {
    'reload_': 'reload'
}

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on systems that are a proxy minion
    '''
    if __grains__['kernel'] == 'proxy':
        return __virtualname__
    return False


def get_all():
    '''
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    proxy_fn = 'rest_sample'+ '.service_list'
    return __opts__['proxymodule'][proxy_fn]()


def start(name):
    '''
    Start the specified service on the rest_sample

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''

    proxy_fn = 'rest_sample'+ '.service_start'
    return __opts__['proxymodule'][proxy_fn](name)


def stop(name):
    '''
    Stop the specified service on the rest_sample

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    proxy_fn = 'rest_sample'+ '.service_stop'
    return __opts__['proxymodule'][proxy_fn](name)


def restart(name):
    '''
    Restart the specified service with rest_sample

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''

    proxy_fn = 'rest_sample'+ '.service_restart'
    return __opts__['proxymodule'][proxy_fn](name)


def status(name, sig):
    '''
    Return the status for a service via rest_sample, returns a bool
    whether the service is running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''

    proxy_fn = 'rest_sample' + '.service_status'
    resp = __opts__['proxymodule'][proxy_fn](name)
    if resp['comment'] == 'stopped':
        return {name: False}
    if resp['comment'] == 'running':
        return {name: True}
